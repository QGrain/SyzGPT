import os
import json
import argparse


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


def repair_line(line):
    line = line.replace('"', '\'')
    if line[-1] == ';':
        line = line[:-1]
    return line


# [RET = ]SYSCALL(ARGS...)
def read_prog(prog_path):
    prog_lines = []
    with open(prog_path, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if '(' in line:
                # line = repair_line(line)
                prog_lines.append(line)
    return prog_lines


def repair_prog_from_str(prog_str):
    new_prog_str = ''
    for line in prog_str.split('\n'):
        line = line.strip()
        if '(' in line:
            line = repair_line(line)
            new_prog_str += '%s\n'%line
    return new_prog_str


def write_prog(prog_lines, prog_path):
    with open(prog_path, 'w') as f:
        for line in prog_lines:
            f.write('%s\n'%line)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Corpus Calibrator')
    parser.add_argument('-i', '--input', type=str, help='path to invalid syz program file or dir')
    parser.add_argument('-s', '--syzkaller', type=str, help='path to syzkaller')
    parser.add_argument('-o', '--output', type=str, help='path to store trimed syz program file or dir')

    args = parser.parse_args()
    
    target = args.input
    dest = args.output
    if os.path.isdir(target):
        check_dir(dest)
    assert(os.path.isfile(target) == os.path.isfile(dest))
    
    # load builtin_syscalls
    project_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    data_dir = os.path.join(project_dir, 'data')
    
    builtin_syscalls = {}
    with open(os.path.join(data_dir, 'builtin_syscalls.json'), 'r') as f:
        builtin_syscalls = json.load(f)
    
    if os.path.isfile(target):
        prog_lines = read_prog(target)
        write_prog(prog_lines, dest)
        exit(0)
    
    total_cnt = 0
    success_cnt = 0
    for fn in os.listdir(target):
        total_cnt += 1
        in_path = os.path.join(target, fn)
        out_path = os.path.join(dest, fn)
        # if os.path.isfile(out_path):
        #     print('Already repair at %s'%out_path)
        #     continue
        try:
            prog_lines = read_prog(in_path)
            write_prog(prog_lines, out_path)
            print('Repair at %s'%out_path)
            success_cnt += 1
        except Exception as e:
            print('Failed to repair %s, Exception: %s'%(in_path, e))
            continue
    print('Done! success %d/%d!'%(success_cnt, total_cnt))