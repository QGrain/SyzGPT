import json
import os
import random
import tiktoken
from time import time

DEF_PROG1 = '''\
r0 = openat$6lowpan_control(0xffffffffffffff9c, &(0x7f00000000c0), 0x2, 0x0)
ioctl$LOOP_SET_FD(r0, 0x4c00, r0) (fail_nth: 5)
write(r0, &AUTO="01010101", 0x4) (async)'''

DEF_PROG2 = '''\
ptrace$setsig(0x4203, 0x0, 0x0, &(0x7f0000000080)={0x41, 0xb07, 0x10001})
socketpair(0x22, 0x2, 0xf5, &(0x7f0000000100))
bind$tipc(0xffffffffffffffff, 0x0, 0x0)
seccomp$SECCOMP_SET_MODE_FILTER(0x1, 0x0, &(0x7f0000000240)={0x0, &(0x7f0000000200)})
ptrace$setsig(0x4203, 0x0, 0x8, &(0x7f0000000280))
accept(0xffffffffffffffff, &(0x7f0000000500)=@pppol2tp={0x18, 0x1, {0x0, 0xffffffffffffffff, {0x2, 0x0, @loopback}}}, 0x0)
fanotify_init(0x10, 0x800)
syz_clone3(&(0x7f0000001a40)={0x82000, &(0x7f0000001780), &(0x7f00000017c0), 0x0, {0x29}, &(0x7f0000001840)=""/205, 0xcd, &(0x7f0000001940)=""/152, 0x0}, 0x58)'''

DEF_PROG3 = '''\
r0 = openat$bifrost(0xffffffffffffff9c, &AUTO='/dev/bifrost\x00', 0x2, 0x0)
ioctl$KBASE_IOCTL_VERSION_CHECK(r0, 0xc0048000, &AUTO={0xB, 0xF})
ioctl$KBASE_IOCTL_SET_FLAGS(r0, 0x40048001, &AUTO={0x0})
mmap$bifrost(nil, 0x3000, 0x3, 0x1, r0, 0x3000)
ioctl$KBASE_IOCTL_MEM_ALLOC(r0, 0xc0208005, &AUTO={0x1, 0x1, 0x0, 0xf, 0x0, 0x0})
close(r0)'''

DEF_PROG4 = '''\
r0 = socket$inet_udp(AUTO, AUTO, AUTO)
bind$inet(r0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
r1 = socket$inet_udp(AUTO, AUTO, AUTO)
sendto$inet(r1, &AUTO=""/10, AUTO, 0x0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
recvfrom(r0, &AUTO=""/10, AUTO, 0x0, 0x0, 0x0)'''


DEF_PROGS = [
    {'ioctl$LOOP_SET_FD': DEF_PROG1},
    {'fanotify_init': DEF_PROG2},
    {'mmap$bifrost': DEF_PROG3},
    {'recvfrom': DEF_PROG4}
]


def rnd(len):
    return random.randint(0, len-1)

def rnd_k(len, k):
    return random.sample(range(0, len), k)


def count_tokens_for_model(string, model_name):
    '''Return the number of tokens in a text string, passing GPT model name'''
    enc = tiktoken.encoding_for_model(model_name)
    return len(enc.encode(string))


def random_choose_variant(syscalls, builtin_syscalls):
    variants = []
    for syscall in syscalls:
        if syscall in builtin_syscalls:
            l = len(builtin_syscalls[syscall])
            variants.append(builtin_syscalls[syscall][rnd(l)]['Name'])
    return variants


def get_related_from_call_depend(variant, call_depend):
    call = variant.split('$')[0]
    related = []
    if call in call_depend:
        l1 = len(call_depend[call]['depend'])
        l2 = len(call_depend[call]['depended'])
        if l1 > 0:
            related.append(call_depend[call]['depend'][rnd(l1)])
        if l2 > 0:
            related.append(call_depend[call]['depended'][rnd(l2)])
    return related


def get_related_from_syz_depend(variant, syz_depend):
    related = []
    if variant in syz_depend:
        l1 = len(syz_depend[variant]['depend'])
        l2 = len(syz_depend[variant]['depended'])
        if l1 > 0:
            related.append(syz_depend[variant]['depend'][rnd(l1)])
        if l2 > 0:
            related.append(syz_depend[variant]['depended'][rnd(l2)])
    return related


def read_prog(prog_path):
    prog_str = ''
    with open(prog_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines:
            if line[0] == '#':
                continue
            prog_str += line
    return prog_str.strip()


def search_programs(variant, reverse_index):
    if variant in reverse_index:
        l = len(reverse_index[variant])
        prog_str = read_prog(reverse_index[variant][rnd(l)])
        return prog_str
    else:
        return ''


def stat_programs(variants, reverse_index):
    prog_stat = []
    l = len(variants)
    if l != 0:
        v = variants[rnd(l)]
        if v in reverse_index:
            l = len(reverse_index[v])
            prog_str = read_prog(reverse_index[v][rnd(l)])
            prog_stat.append(v)
            prog_stat.append(count_tokens_for_model(prog_str, 'gpt-3.5-turbo'))
            prog_stat.append(prog_str)
    return prog_stat


def get_multi_layer_depend(variant, depends, depend_type=1, n_layer=3):
    # as depended is useless in related selection, so it can be skipped to improve efficiency
    multi_depend = {'depend': {}, 'depended': {}}
    # type 1 for syz_depend, type 2 for call_depend
    if depend_type == 2:
        variant = variant.split('$')[0]

    # layer 1
    if variant in depends:
        multi_depend['depend'][1] = depends[variant]['depend']
        multi_depend['depended'][1] = depends[variant]['depended']
    else:
        multi_depend['depend'][1] = []
        multi_depend['depended'][1] = []
        
    # layer 2~n
    for i in range(2, n_layer+1):
        multi_depend['depend'][i] = []
        for v in multi_depend['depend'][i-1]:
            for d in depends[v]['depend']:
                if d != variant and d not in multi_depend['depend'][i]:
                    multi_depend['depend'][i].append(d)
        multi_depend['depended'][i] = []
        for v in multi_depend['depended'][i-1]:
            for ded in depends[v]['depended']:
                if ded != variant and ded not in multi_depend['depended'][i]:
                    multi_depend['depended'][i].append(ded)
    
    return multi_depend    


def random_choose_prog(multi_depend, builtin_syscalls, depend_type, each_num=2):
    l1_num = len(multi_depend['depend'][1])
    l2_num = len(multi_depend['depend'][2])
    shuf_idx1 = [i for i in range(l1_num)]
    shuf_idx2 = [i for i in range(l2_num)]
    random.shuffle(shuf_idx1)
    random.shuffle(shuf_idx2)

    l1_progs, l2_progs = [], []
    for i in shuf_idx1:
        v = multi_depend['depend'][1][i]
        if depend_type == 2:
            v = random_choose_variant([v], builtin_syscalls)[0]
        prog_str = search_programs(v, reverse_index)
        if prog_str:
            l1_progs.append({v: prog_str})
        if len(l1_progs) == each_num:
            break
    for i in shuf_idx2:
        v = multi_depend['depend'][2][i]
        if depend_type == 2:
            v = random_choose_variant([v], builtin_syscalls)[0]
        prog_str = search_programs(v, reverse_index)
        if prog_str:
            l2_progs.append({v: prog_str})
        if len(l2_progs) == each_num:
            break
    return l1_progs, l2_progs


t0 = time()

with open('uncovered/fuzz-1h_uncovered_variants.txt', 'r') as f:
    target_variants = [line.strip() for line in f.readlines()]

with open('call_dependencies/call_dependencies_all.json', 'r') as f:
    call_depend = json.load(f)

with open('syz_dependencies/syz_depend_inout.json', 'r') as f:
    syz_depend = json.load(f)
    
with open('./builtin_syscalls.json', 'r') as f:
    builtin_syscalls = json.load(f)
    
with open('/root/corpus/enriched-corpus-1106_rev_index.json', 'r') as f:
    reverse_index = json.load(f)

print(len(call_depend), len(syz_depend))


zero_list = []
ht = {}
shot = 3
for variant in target_variants:
    multi_syz_depend = get_multi_layer_depend(variant, syz_depend, 1)
    multi_call_depend = get_multi_layer_depend(variant, call_depend, 2)
    
    l1_progs_from_syz, l2_progs_from_syz = random_choose_prog(multi_syz_depend, builtin_syscalls, 1, 2)
    l1_progs_from_call, l2_progs_from_call = random_choose_prog(multi_call_depend, builtin_syscalls, 2, 2)
    search_cnt = 0
    related_progs = DEF_PROGS.copy()
    if len(l2_progs_from_syz) == 0:
        for p in l1_progs_from_syz:
            related_progs[search_cnt] = p
            search_cnt += 1
    elif len(l1_progs_from_syz) == 0:
        for p in l2_progs_from_syz:
            related_progs[search_cnt] = p
            search_cnt += 1
    else:
        related_progs[0] = l1_progs_from_syz[0]
        related_progs[1] = l2_progs_from_syz[0]
        search_cnt = 2

    try:
        for p in l2_progs_from_call:
            related_progs[search_cnt] = p
            search_cnt += 1
            if search_cnt == shot:
                raise Exception
        for p in l1_progs_from_call:
            related_progs[search_cnt] = p
            search_cnt += 1
            if search_cnt == shot:
                raise Exception
    except:
        pass
    if variant == 'sendmsg$qrtr':
        print('%s:'%variant)
        print('\tlayer-1 syz depend:', multi_syz_depend['depend'][1])
        print('\tlayer-2 syz depend:', multi_syz_depend['depend'][2])
        print('%s:'%(variant.split('$')[0]))
        print('\tlayer-1 %d depend:'%(len(multi_call_depend['depend'][1])), multi_call_depend['depend'][1])
        print('\tlayer-2 %d depend:'%(len(multi_call_depend['depend'][2])), multi_call_depend['depend'][2])

    # if search_cnt < shot:
    #     if len(l1_progs_from_call) + len(l2_progs_from_call) > 0:
    #         print('%s, after call, search_cnt == %d, len(l1_syz)=%d, len(l2_syz)=%d, len(l1_call)=%d, len(l2_call)=%d'%(variant, search_cnt, len(l1_progs_from_syz), len(l2_progs_from_syz), len(l1_progs_from_call), len(l2_progs_from_call)))
        # for p in l1_progs_from_syz:
        #     print(p)
        # for p in l2_progs_from_syz:
        #     print(p)
        # print('%s:'%variant)
        # print('\tlayer-1 syz depend:', multi_syz_depend['depend'][1])
        # print('\tlayer-2 syz depend:', multi_syz_depend['depend'][2])
    if search_cnt not in ht:
        ht[search_cnt] = 1
    else:
        ht[search_cnt] += 1
    # for i in range(search_cnt):
    #     print(related_progs[i])
    # print('%s:'%(variant.split('$')[0]))
    # print('\tlayer-1 %d depend:'%(len(multi_call_depend['depend'][1])), multi_call_depend['depend'][1])
    # print('\tlayer-2 %d depend:'%(len(multi_call_depend['depend'][2])), multi_call_depend['depend'][2])
    
        
    #     layer2_depend_prog = search_programs(multi_syz_depend['depend'][2][rnd(l2_syz_num)])
    # layer1_depend_prog = search_programs(multi_syz_depend['depend'][1][rnd(l1_syz_num)])
    # layer2_depend_prog = search_programs(multi_syz_depend['depend'][2][rnd(l2_syz_num)])
    
    
    # related_calls = get_related_from_call_depend(variant, call_depend)
    # related_calls2var = random_choose_variant(related_calls, builtin_syscalls)
    # related_variants = get_related_from_syz_depend(variant, syz_depend)
    # to_search_variants = set(related_calls2var) | set(related_variants)
    # progs = {}
    # for variant in to_search_variants:
    #     prog = search_programs(variant, reverse_index)
    #     if prog:
    #         progs[variant] = prog
    
    # if len(progs) == 4:
    #     print('%s'%variant)
    #     print('\trelated calls:', related_calls)
    #     print('\trelated calls2var:', related_calls2var)
    #     print('\trelated variants:', related_variants)
    #     for var in progs:
    #         print('\nprog of %s:'%var)
    #         print(progs[var])
    # if related_calls == [] and related_variants == []:
    #     zero_list.append(variant)

# print(zero_list)
# print(len(zero_list))


for shash in ht:
    print('%s: %d'%(shash, ht[shash]))

print('[Done] Cost %.2fs'%(time()-t0))