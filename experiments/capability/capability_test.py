import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import openai
import argparse
from generator.utils import *
from generator.gpt_wrapper import *
try:
    from generator.private_config import *
except ImportError:
    from generator.config import *
from generator.prompts import *
from time import time, sleep

CAPA_DIR = './capabilities'


TEST1_PROMPT = '''\
Please tell me the SYNOPSIS (C format) of linux system call "%s"'''

TEST3_PROMPT = '''\
User: Generate a syz program (syzkaller style) that contains the syscall "fanotify_init", don't make small talk.
Assistant: 
ptrace$setsig(0x4203, 0x0, 0x0, &(0x7f0000000080)={0x41, 0xb07, 0x10001})
socketpair(0x22, 0x2, 0xf5, &(0x7f0000000100))
bind$tipc(0xffffffffffffffff, 0x0, 0x0)
seccomp$SECCOMP_SET_MODE_FILTER(0x1, 0x0, &(0x7f0000000240)={0x0, &(0x7f0000000200)})
ptrace$setsig(0x4203, 0x0, 0x8, &(0x7f0000000280))
accept(0xffffffffffffffff, &(0x7f0000000500)=@pppol2tp={0x18, 0x1, {0x0, 0xffffffffffffffff, {0x2, 0x0, @loopback}}}, 0x0)
fanotify_init(0x10, 0x800)
syz_clone3(&(0x7f0000001a40)={0x82000, &(0x7f0000001780), &(0x7f00000017c0), 0x0, {0x29}, &(0x7f0000001840)=""/205, 0xcd, &(0x7f0000001940)=""/152, 0x0}, 0x58)

User: Generate a syz program (syzkaller style) that contains the syscall "mmap$bifrost", don't make small talk.
Assistant: 
r0 = openat$bifrost(0xffffffffffffff9c, &AUTO='/dev/bifrost\x00', 0x2, 0x0)
ioctl$KBASE_IOCTL_VERSION_CHECK(r0, 0xc0048000, &AUTO={0xB, 0xF})
ioctl$KBASE_IOCTL_SET_FLAGS(r0, 0x40048001, &AUTO={0x0})
mmap$bifrost(nil, 0x3000, 0x3, 0x1, r0, 0x3000)
ioctl$KBASE_IOCTL_MEM_ALLOC(r0, 0xc0208005, &AUTO={0x1, 0x1, 0x0, 0xf, 0x0, 0x0})
close(r0)

User: Generate a syz program (syzkaller style) that contains the syscall "sendto$inet", don't make small talk.
Assistant: 
r0 = socket$inet_udp(AUTO, AUTO, AUTO)
bind$inet(r0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
r1 = socket$inet_udp(AUTO, AUTO, AUTO)
sendto$inet(r1, &AUTO=""/10, AUTO, 0x0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
recvfrom(r0, &AUTO=""/10, AUTO, 0x0, 0x0, 0x0)

User: Generate a syz program (syzkaller style) that contains the syscall "%s", don't make small talk.
Assistant:
'''


def store_text(res, fpath):
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(res)
        

def extract_synopsis(res):
    # we suppose the synopsis are included in the first code block wrapped with ``` and ```
    synop_found = 0
    synopsis = ''
    lines = res.split('\n')
    for line in lines:
        line = line.strip()
        if line == '':
            continue
        if line[:3] == '```':
            synop_found ^= 1
            if synop_found == 0:
                # break when the first code block ends
                break
            else:
                continue
        if synop_found == 1:
            synopsis += line + '\n'
    return synopsis


def load_synopsis_from_man(man_path):
    with open(man_path, 'r') as f:
        man_doc = json.load(f)
    
    try:
        synopsis = man_doc['SYNOPSIS']
    except:
        synopsis = ''
    return synopsis
    

def replace_unprintables(s):
    new_s = ''
    for c in s:
        if not c.isprintable() and c != chr(0x0a):
            new_s += '\\x{:02x}'.format(ord(c))
        else:
            new_s += c
    return new_s


def rnd(len):
    return random.randint(0, len-1)


if __name__ == '__main__':
    t0 = time()
    parser = argparse.ArgumentParser(description='Capability Test (test1~3)')
    parser.add_argument('-t', '--test', type=str, help='test, from 1~3')
    parser.add_argument('-S', '--sample_step', type=int, help='sample syscall from file every S steps')
    parser.add_argument('-v', '--variant_mode', action='store_true', help='variant mode, specify with -c or -f when targets are variants')
    args = parser.parse_args()
    
    test = args.test
    check_dir(os.path.join(CAPA_DIR, test))
    
    with open('../crawler/syscall_from_manpage.txt', 'r') as f:
        syscalls = [line.strip() for line in f.readlines()]

    with open('../data/covered/builtin_variants.txt', 'r') as f:
        syscall_variants = [line.strip() for line in f.readlines()]
    
    with open('../data/builtin_syscalls.json', 'r') as f:
        builtins = json.load(f)
    
    if test == '1' or test == 'test1':
        # test1: query LLM about the SYNOPSIS of target syscalls
        # python capability_test.py -t 1
        i = 0
        no_synop_cnt = 0
        total_tokens = 0
        for syscall in syscalls:
            # sleep(1)
            i += 1
            fn_synopsis = os.path.join(CAPA_DIR, test, '%s.synopsis'%syscall)
            if os.path.isfile(fn_synopsis):
                print('[%d][%.2fs][*] already query %s'%(i, (time()-t0), syscall))
                continue
            # msg_with_hist = [{"role": "system", "content": "Only output the required sequence or program without any other explanation words."}]
            msg_with_hist = []
            query = TEST1_PROMPT%syscall
            res, tokens = query_with_history(msg_with_hist, query, LLM_MODEL, True, 0.2)
            total_tokens += tokens
            # print('[%d tokens] [Response]:\n%s'%(tokens, res))
            synopsis = extract_synopsis(res)
            
            fn_response = os.path.join(CAPA_DIR, test, '%s_%d.response'%(syscall, tokens))
            store_text(res, fn_response)
            print('[%d][%.2fs][%dtks][+] query of %s done, cost %d tokens'%(i, (time()-t0), total_tokens, syscall, tokens))
            if synopsis:
                store_text(synopsis, fn_synopsis)
            else:
                print('[%d][%.2fs][%dtks][x] synopsis of %s is None'%(i, (time()-t0), total_tokens, syscall))
                no_synop_cnt += 1
                
        print('Cost %.2fs and %d tokens, %d have no synopsis'%((time()-t0), total_tokens, no_synop_cnt))
    elif test == '3' or test == 'test3':
        # test3: Ask LLM to generate syz program with few-shot learning
        i = 0
        no_out = 0
        total_tokens = 0
        # notice: here is variant
        for call in builtins:
            syscall = builtins[call][0]["Name"]
            i += 1
            already_gen = 0
            for fn in os.listdir(os.path.join(CAPA_DIR, test)):
                syscall_name = ''
                splt = fn.split('_')[:-1]
                for s in splt:
                    syscall_name += s + '_'
                syscall_name = syscall_name[:-1]
                if syscall == syscall_name:
                    print('[%d][%.2fs][*] already query %s at %s'%(i, (time()-t0), syscall, fn))
                    already_gen = 1
                    break
            if already_gen == 1:
                continue
            if args.sample_step and i % args.sample_step != 1:
                continue
            sleep(10)
            # msg_with_hist = [{"role": "system", "content": "Only output the required sequence or program without any other explanation words."}]
            msg_with_hist = []
            query = TEST3_PROMPT%syscall
            res, tokens = query_with_history(msg_with_hist, query, LLM_MODEL, True, 0.2)
            res = replace_unprintables(res)
            total_tokens += tokens
            # print('[%d tokens] [Response]:\n%s'%(tokens, res))
            print('[%d][%.2fs][%dtks][+] query of %s done, cost %d tokens'%(i, (time()-t0), total_tokens, syscall, tokens))
            fn_prog = os.path.join(CAPA_DIR, test, '%s_%d.prog'%(syscall, tokens))
            if res:
                store_text(res, fn_prog)
            else:
                print('[%d][%.2fs][%dtks][x] output of %s is None'%(i, (time()-t0), total_tokens, syscall))
                no_out += 1
                
        print('Cost %.2fs and %d tokens, %d have no output'%((time()-t0), total_tokens, no_out))
    else:
        print('[X] Invalid -t value: %s'%test)