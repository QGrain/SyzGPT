import argparse, os, json
import shutil
from time import time


def read_prog(path):
    with open(path, 'r') as f:
        prog_str = f.read()
    return prog_str


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


def find_all(s, c):
    res = []
    for i in range(len(s)):
        if s[i] == c:
            res.append(i)
    return res


def replace_k(s, k, v):
    new_s = ''
    for i in range(len(s)):
        if i != k:
            new_s += s[i]
        else:
            new_s += v
    return new_s


def fn2call(fn, enabled_calls):
    syscalls = []
    for call in enabled_calls:
        syscall = call.split('$')[0]
        if syscall not in syscalls:
            syscalls.append(syscall)

    raw_call = fn.split('.prog')[0]
    if raw_call in enabled_calls:
        return raw_call
    all_idx = find_all(raw_call, '_')
    for i in all_idx[::-1]:
        call = replace_k(raw_call, i, '$')
        s1, s2 = call.split('$')[0], call.split('$')[1]
        if call in enabled_calls:
            return call
        if s1 in syscalls:
            idx2 = find_all(s2, '_')
            for j in idx2:
                s2_ = replace_k(s2, j, '$')
                call_ = s1 + '$' + s2_
                if call_ in enabled_calls:
                    return call_
            
    print('%s return None, len(enabled_calls)=%d'%(fn, len(enabled_calls)))
    return None


def get_args():
    parser = argparse.ArgumentParser(description='Check valid rate of generation programs')
    parser.add_argument('-H', '--generation_history', type=str, help='generation history')
    parser.add_argument('-g', '--generated_dir', type=str, help='dir of generated programs')
    parser.add_argument('-e', '--enabled_calls', type=str, help='enabled calls')
    parser.add_argument('-t', '--target_calls', type=str, help='uncovered target calls')
    parser.add_argument('-o', '--trimed_dir', type=str, help='trimed dir for valid target calls')
    parser.add_argument('-b', '--blacklist_calls', type=str, nargs='*', help='black list of calls')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    t0 = time()
    args = get_args()
    blacklist_calls = args.blacklist_calls or []
    assert(args.generated_dir)
    
    
    if args.enabled_calls:
        with open(args.enabled_calls, 'r') as f:
            enabled_calls = [line.strip() for line in f.readlines()]
    else:
        enabled_calls = []
    
    if args.trimed_dir:
        check_dir(args.trimed_dir)
    
    if args.target_calls:
        with open(args.target_calls, 'r') as f:
            target_calls = [line.strip() for line in f.readlines()]
    
    
    cnt = 0
    valid_cnt = 0
    target_cnt = 0
    if args.generation_history:
        with open(args.generation_history, 'r') as f:
            gen_his = json.load(f)
        for call in gen_his:
            if call in blacklist_calls or (enabled_calls and call not in enabled_calls):
                continue
            cnt += 1
            fpath = os.path.join(args.generated_dir, gen_his[call][0])
            prog_str = read_prog(fpath)
            if len(prog_str) == 0:
                print('%s has len 0, continue'%fpath)
                continue
            if call in prog_str:
                valid_cnt += 1
                if args.target_calls and call in target_calls:
                    target_cnt += 1
                    if args.trimed_dir:
                        new_fpath = os.path.join(args.trimed_dir, gen_his[call][0])
                        shutil.copyfile(fpath, new_fpath)
    else:
        assert(args.enabled_calls)
        for fn in os.listdir(args.generated_dir):
            cnt += 1
            call = fn2call(fn, enabled_calls)
            fpath = os.path.join(args.generated_dir, fn)
            prog_str = read_prog(fpath)
            if len(prog_str) == 0:
                print('%s has len 0, continue'%fpath)
                continue
            if call in prog_str:
                valid_cnt += 1
                if args.target_calls and call in target_calls:
                    target_cnt += 1
            
    print('Done! Cost %.2fs. %d/%d programs contain the target syscall in program. %d of them are for target calls'%(time()-t0, valid_cnt, cnt, target_cnt))