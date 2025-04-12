import os
import re
import json
import argparse
import concurrent.futures
import tiktoken
from time import time


'''
data structure of `syscalls`: 
syscalls = {
    "call": {
        "variant": cnt,
        "variant2", cnt2,
        ...
    },
    "call2":{
        ...
    },
    ...
}
'''


PROG_LEN_THRESHOLD = 900
CALL_THRESHOLD = 36
REPEAT_ARG = 2


def extract_syscalls(s, syscalls):
    var_calls = re.findall(r'(?<![\\])\b([A-Za-z_]*(?:\$)?[A-Za-z0-9_]+)\(', s)
    valid_variants = []
    for variant in var_calls:
        if variant == '' or variant.isdigit():
            continue
        valid_variants.append(variant)
        call = variant.split('$')[0]
        if call == '':
            continue
        if call not in syscalls:
            syscalls[call] = {variant: 1}
        else:
            if variant not in syscalls[call]:
                syscalls[call][variant] = 1
            else:
                syscalls[call][variant] += 1
    # return len(valid_variants), len(set(valid_variants))
    return valid_variants


def analyze_all(dir, build_reverse=False):
    syscalls = {}
    reverse_index = {}
    seq_lens, variant_cnts = [], []
    for prog in os.listdir(dir):
        fpath = os.path.join(dir, prog)
        prog_str = read_prog(fpath)
        if prog_str:
            valid_variants = extract_syscalls(prog_str, syscalls)
            l, n = len(valid_variants), len(set(valid_variants))
            if l >= CALL_THRESHOLD:
                l = n * REPEAT_ARG
            seq_lens.append(l)
            variant_cnts.append(n)
            
            # build reverse_index, abandon those prog with more than 500 tokens
            if build_reverse == False:
                continue
            if len(prog_str) < PROG_LEN_THRESHOLD:     
                for variant in set(valid_variants):
                    if variant not in reverse_index:
                        reverse_index[variant] = [fpath]
                    else:
                        reverse_index[variant].append(fpath)

    if build_reverse == True:
        if dir[-1] == '/':
            dir = dir[:-1]
        corpus_name = os.path.basename(dir)
        prefix_dir = os.path.dirname(dir)
        reverse_index_fn = os.path.join(prefix_dir, corpus_name+'_rev_index.json')
        with open(reverse_index_fn, 'w') as f:
            json.dump(reverse_index, f, indent=4)
    return syscalls, seq_lens, variant_cnts


def read_prog(prog_path):
    prog_str = ''
    with open(prog_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines:
            if line[0] == '#':
                continue
            prog_str += line
    return prog_str.strip()


def count_tokens_for_model(string, model_name):
    '''Return the number of tokens in a text string, passing GPT model name'''
    enc = tiktoken.encoding_for_model(model_name)
    return len(enc.encode(string))


def stat_dict(d, to_file=None):
    pprint_str = json.dumps(d, indent=4, ensure_ascii=False)
    print(pprint_str)
    if to_file:
        with open(to_file, "a", encoding="utf-8") as f:
            f.write("%s\n"%pprint_str)


def stat_seq_lens(sl):
    lhash = [0] * 1024
    for l in sl:
        lhash[l] += 1

    x, y = [], []
    for i in range(len(lhash)):
        if lhash[i] != 0:
            print('lhash[%d]=%d'%(i, lhash[i]))
            x.append(i)
            y.append(lhash[i])
    print('\n')
    return x, y


def diff_syscalls(s1, s2):
    u1, u2 = [], []
    for c1 in s1:
        if c1 not in s2:
            u1.append(c1)
    for c2 in s2:
        if c2 not in s1:
            u2.append(c2)
    return u1, u2


def analyze_directory(d):
    print('[+] start analyze task for %s'%d)
    syscalls, _, _ = analyze_all(d)
    n_variants = 0
    for call in syscalls:
        n_variants += len(syscalls[call])
    return len(syscalls), n_variants


def print_t(s, t):
    print('[%.2fs] %s'%(time()-t, s))


def main():
    t0 = time()
    parser = argparse.ArgumentParser(description='corpus analyzer')
    parser.add_argument('action', type=str, help='analyze | plot')
    parser.add_argument('-d', '--directory', type=str, nargs='+', help='unpacked directory(s)')
    parser.add_argument('-b', '--build_reverse', action='store_true', help='save the results')
    parser.add_argument('-s', '--store', action='store_true', help='save the results')
    parser.add_argument('-D', '--DEBUG', action='store_true', help='print DEBUG info')

    args = parser.parse_args()
    
    print_t('get args', t0)
    
    if not args.directory:
        print_t('ERROR: you need to specify corpus directory through -d', t0)
        exit(1)
    
    if args.action == 'analyze':
    # recommond to use shell script to parallelize rather than specify multi-dir at one time, like:
    # python corpus_analyzer.py analyze -d corpus_dir1 &
    # python corpus_analyzer.py analyze -d corpus_dir2 &
        for d in args.directory:
            print_t('stat for corpus dir %s'%d, t0)
            syscalls, seq_lens, variant_cnts = analyze_all(d, args.build_reverse)
            
            n_variants = 0
            if args.store:
                if d[-1] == '/':
                    dn = d[:-1]
                else:
                    dn = d
                dd = os.path.dirname(dn)
                dn = os.path.basename(dn)
                syscalls_path = os.path.join(dd, '%s_syscalls.txt'%dn)
                variants_path = os.path.join(dd, '%s_variants.txt'%dn)
                f1 = open(syscalls_path, 'w', encoding='utf-8')
                f2 = open(variants_path, 'w', encoding='utf-8')
                for call in syscalls:
                    f1.write('%s\n'%call)
                    n_variants += len(syscalls[call])
                    for variant in syscalls[call]:
                        f2.write('%s\n'%variant)
                
                print_t('store syscalls to %s and %s'%(variants_path, syscalls_path), t0)
            else:
                for call in syscalls:
                    n_variants += len(syscalls[call])
            
            avg_len = 0
            avg_var_cnt = 0
            seeds_num = len(seq_lens)
            seq_len_distri = {0:0, 1:0, 2:0, 3:0, 4:0, '5+':0}
            for i in range(seeds_num):
                avg_len += seq_lens[i]/seeds_num
                avg_var_cnt += variant_cnts[i]/seeds_num
                if seq_lens[i] >= 5:
                    seq_len_distri['5+'] += 1
                else:
                    seq_len_distri[seq_lens[i]] += 1

            print_t('corpus size: %d, syscalls: %d, variants: %d'%(seeds_num, len(syscalls), n_variants), t0)
            if seeds_num != 0:
                print_t('avg_seq_len = %.3f, avg_variant_cnt = %.3f'%(avg_len, avg_var_cnt), t0)
                print_t('max_seq_len = %d, max_variant_cnt = %d'%(max(seq_lens), max(variant_cnts)), t0)
                for k in seq_len_distri:
                    print('seq_len=%s: %d (%.2f%%)'%(k, seq_len_distri[k], seq_len_distri[k]*100/seeds_num))
            else:
                print_t('seeds_num = 0, no other metrics', t0)
            
            if args.DEBUG:
                # print the number of syscalls[call][variants]
                print_t('print the distributions of variants', t0)
                for call in syscalls:
                    for variant in syscalls[call]:
                        print('[%s][%s]: %d'%(call, variant, syscalls[call][variant]))

    elif args.action == 'plot':
        n_calls_seq, n_variants_seq = [], []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_dir = {executor.submit(analyze_directory, d): d for d in args.directory}
            for future in concurrent.futures.as_completed(future_to_dir):
                d = future_to_dir[future]
                try:
                    n_calls, n_variants = future.result()
                    n_calls_seq.append(n_calls)
                    n_variants_seq.append(n_variants)
                    print(f'Stat for corpus dir {d} - n_calls: {n_calls}, n_variants: {n_variants}')
                except Exception as e:
                    print(f'Error analyzing directory {d}: {e}')

        n_calls_seq.sort()
        n_variants_seq.sort()
        print(n_calls_seq)
        print(n_variants_seq)
        # do plot with n_calls_seq and n_variants_seq seperatively.
    else:
        print_t('[ERROR] unknown action', t0)
        return

    print_t('Done!', t0)


if __name__ == '__main__':
    main()