import argparse, os
from time import time


def read_prog(path):
    with open(path, 'r') as f:
        prog_str = f.read()
    return prog_str


def get_args():
    parser = argparse.ArgumentParser(description='Check valid rate of generation programs')
    parser.add_argument('-g', '--generated_dir', type=str, help='dir of generated programs')
    parser.add_argument('-t', '--target_calls', type=str, help='uncovered target calls')
    parser.add_argument('-e', '--enabled_calls', type=str, help='enabled calls')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    t0 = time()
    args = get_args()
    assert(args.generated_dir)
    assert(args.target_calls)

    with open(args.target_calls, 'r') as f:
        target_calls = [line.strip() for line in f.readlines()]
    
    contain_cnt = 0
    uncovered_syscalls = []
    for syscall in target_calls:
        find = 0
        for fn in os.listdir(args.generated_dir):
            fpath = os.path.join(args.generated_dir, fn)
            prog_str = read_prog(fpath)
            if len(prog_str) == 0:
                print('%s has len 0, continue'%fpath)
                continue
            if '%s('%syscall in prog_str:
                contain_cnt += 1
                find = 1
                break
        if find == 0:
            uncovered_syscalls.append(syscall)
            
    print('Done! Cost %.2fs. %d/%d syscalls are contained in the generated programs.'%(time()-t0, contain_cnt, len(target_calls)))
    print(sorted(uncovered_syscalls))
    
    enabled_calls = []
    if args.enabled_calls:
        with open(args.enabled_calls, 'r') as f:
            enabled_calls = [line.strip() for line in f.readlines()]
    disabled_cnt = 0
    if enabled_calls != []:
        for syscall in uncovered_syscalls:
            if syscall not in enabled_calls:
                disabled_cnt += 0
    print('%d of the uncovered syscalls are actually disabled syscalls'%disabled_cnt)