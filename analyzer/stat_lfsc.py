import os
import argparse
from time import time


def read_covered_calls(covered_fpath):
    covered_calls = []
    with open(covered_fpath, 'r') as f:
        covered_calls = [line.strip() for line in f.readlines()]
    return covered_calls


def read_builtin_calls():
    builtin_calls = []
    with open(os.path.join('../data/builtin_variants.txt'), 'r') as f:
        builtin_calls = [line.strip() for line in f.readlines()]
    return builtin_calls


def stat_lfsc(builtin_calls, all_covered_calls, stat_type):
    lfsc = []
    builtin_set = set(builtin_calls)
    # type 1: all uncovered as LFSC
    if stat_type == 1:
        all_covered_set = set([])
        for covered_calls in all_covered_calls:
            covered_set = set(covered_calls)
            all_covered_set |= covered_set
        print(f'[*] The union of these covered calls are {len(all_covered_set)}')
        lfsc = list(builtin_set-all_covered_set)
    # type 2: at least one uncovered as LFSC
    elif stat_type == 2:
        common_covered_set = builtin_set.copy()
        for covered_calls in all_covered_calls:
            covered_set = set(covered_calls)
            common_covered_set &= covered_set
        print(f'[*] The common of these covered calls are {len(common_covered_set)}')
        lfsc = list(builtin_set-common_covered_set)
    # type 3: choose the first uncovered calls as LFSC
    elif stat_type == 3:
        first_covered_set = set(all_covered_calls[0])
        lfsc = list(builtin_set-first_covered_set)
    # type 4: all uncovered + only one covered as LFSC
    elif stat_type == 4:
        builtin_hash = {call:0 for call in builtin_calls}
        for covered_calls in all_covered_calls:
            for call in covered_calls:
                builtin_hash[call] += 1
        for call in builtin_hash:
            if builtin_hash[call] <= 1:
                lfsc.append(call)
    print(f'[+] Stat there are {len(lfsc)} LFSC')
    return lfsc

t0 = time()
parser = argparse.ArgumentParser(description='stat LFSC')
parser.add_argument('-f', '--covered_fpaths', type=str, nargs='+', help='fpaths of coveredCalls')
parser.add_argument('-t', '--stat_type', type=int, default=4, help='type of stat (1, 2, 3, 4)')
parser.add_argument('-o', '--out_name', type=str, default='default_out', help='out name')
args = parser.parse_args()


builtin_calls = read_builtin_calls()
print(f'[+] Read {len(builtin_calls)} builtin calls')

all_covered_calls = []
for fpath in args.covered_fpaths:
    covered_calls = read_covered_calls(fpath)
    all_covered_calls.append(covered_calls)
    print(f'[+] Read {len(covered_calls)} covered calls for {fpath}')


print(f'[*] Your are stating LFSC through type {args.stat_type}')
lfsc = stat_lfsc(builtin_calls, all_covered_calls, args.stat_type)

with open(f'{args.out_name}_lfsc_type{args.stat_type}', 'w') as f:
    for call in lfsc:
        f.write(f'{call}\n')