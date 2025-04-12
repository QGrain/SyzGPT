'''
Sample Usages:

(1) diff syscall list with builtin syscall list: 
$ python diff_corpus.py -l1 ../data/covered/fuzz-1h_syscalls.txt -l2 ../data/covered/builtin_syscalls.txt [-o ../data/uncovered/fuzz-1h_uncovered_syscalls.txt]

(2) diff variant list with builtin variant list:
$ python diff_corpus.py -l1 ../data/covered/fuzz-1h_variants.txt -l2 ../data/covered/builtin_variants.txt -v [-o ../data/uncovered/fuzz-1h_uncovered_variants.txt]

(3) -o output option can be omited for test
'''

import argparse
import json
from time import time
from corpus_analyzer import *


def read_syscalls(path):
    calls_list = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if line:
            calls_list.append(line)
    return calls_list


def read_variants(path):
    syscalls = {}
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines:
        variant = line.strip()
        call = variant.split('$')[0]
        if call not in syscalls:
            syscalls[call] = set([variant])
        else:
            syscalls[call].add(variant)
    return syscalls


def diff_syscalls(l1, l2):
    # l2 is the comparison baseline by default
    diff = []
    for c in l2:
        if c not in l1:
            diff.append(c)
    return diff


def diff_variants(s1, s2):
    # s2 is the comparison baseline by default
    diff = set([])
    call_cover = {}
    zero_cover, non_complete_cover = 0, 0
    for c in s2:
        if c not in s1:
            diff = diff | s2[c]
            call_cover[c] = 0
            zero_cover += 1
        else:
            diff = diff | (s2[c]-s1[c])
            call_cover[c] = len(s1[c])/len(s2[c])*100

    sorted_call_cover = sorted(call_cover.items(), key=lambda x: x[1], reverse=True)
    assert(len(sorted_call_cover) == len(call_cover))
    for one in sorted_call_cover:
        if one[1] < 100:
            print('%s\'s variant coverage = %.2f%%'%(one[0], one[1]))
            non_complete_cover += 1
    print('[Summary] s1 has %d and s2 has %d, %d are totally uncovered, %d are not completely covered.'%(len(s1), len(s2), zero_cover, non_complete_cover))
    return diff, call_cover


def cover_analysis(cover, n):
    zeros, hundreds, sames, diffs = {}, {}, {}, {}
    
    for i in range(n):
        
        for c in cover:
            # initialize zeros, hundreds, sames, diffs
            if len(set(cover[c])) == 1:
                sames[c] = cover[c]
                if sum(cover[c]) == 0:
                    zeros[c] = cover[c]
                elif sum(cover[c]) == 100*n:
                    hundreds[c] = cover[c]
            else:
                diffs[c] = cover[c]
    
    # count uncovered, covered, partial_covered
    print('uncovered covered par_covered')
    for i in range(n):
        uncovered, covered, par_coverd = 0, 0, 0
        all_avg, diff_avg = 0, 0
        for c in cover:
            if cover[c][i] == 0:
                uncovered += 1
            elif cover[c][i] == 100:
                covered += 1
            else:
                par_coverd += 1
        print('%d\t  %d\t  %d'%(uncovered, covered, par_coverd))
    
    # calc all_avg
    print('all_avg coverage')
    for i in range(n):
        all_avg = 0
        for c in cover:
            all_avg += cover[c][i]
        print('%.3f%%'%(all_avg/len(cover)))
        
    # calc diff_avg
    print('diff_avg coverage')
    if diffs:
        for i in range(n):
            diff_avg = 0
            for c in diffs:
                diff_avg += diffs[c][i]
            print('%.3f%%'%(diff_avg/len(diffs)))
    else:
        print('diffs is {}')
        
    # stat max_cnt
    print('max_cnt in diffs')
    if diffs:
        for i in range(n):
            max_cnt = 0
            for c in diffs:
                if max(diffs[c]) == diffs[c][i]:
                    max_cnt += 1
            print('%d'%max_cnt)
    else:
        print('diffs is {}')


if __name__ == '__main__':
    t0 = time()
    parser = argparse.ArgumentParser(description='diff syscalls')
    parser.add_argument('-l1', '--syscall_lists', type=str, nargs='+', help='syscall list of corpus 1')
    parser.add_argument('-l2', '--syscall_list2', type=str, help='syscall list of corpus 2, builtin by default')
    parser.add_argument('-v', '--variant', action='store_true', help='diff the variants')
    parser.add_argument('-o', '--out', type=str, help='save variant coverage to output')

    args = parser.parse_args()
    
    print_t('get args', t0)
    
    assert(args.syscall_lists)
    assert(args.syscall_list2)
    
    variant_cover = {}
    for syscall_list1 in args.syscall_lists:
        if args.variant:
            s1 = read_variants(syscall_list1)
            s2 = read_variants(args.syscall_list2)
            diff, cover = diff_variants(s1, s2)
            for c in cover:
                if c not in variant_cover:
                    variant_cover[c] = [cover[c]]
                else:
                    variant_cover[c].append(cover[c])
        else:
            l1 = read_syscalls(syscall_list1)
            l2 = read_syscalls(args.syscall_list2)
            diff = diff_syscalls(l1, l2)
    
    if args.out:
        out_file = args.out
        if len(out_file) < 5 or out_file[-5:] != '.json':
            out_file = out_file + '.json'
        with open(out_file, 'w') as f:
            json.dump(variant_cover, f, indent=4)
        print('[Info] Store to out_file: %s'%out_file)

    # analyze coverage stats
    cover_analysis(variant_cover, len(args.syscall_lists))

    print_t('Done!', t0)