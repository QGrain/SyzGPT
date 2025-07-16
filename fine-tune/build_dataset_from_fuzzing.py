# Note: This is a script without localization removal
# Currently, it is placed here just for backup purposes

import os
import shutil
import json
import argparse
from time import time
from math import sqrt
from random import randint

config = {
    "max_thres": 1000, # coverage threshold
    "min_thres": 30,   # coverage threshold
    "min_sample_thres_per_syscall": 7,
    "max_sample_per_syscall": 16
}

# We should add more variations of the question template to make the model generate more diverse programs.
# This is the original question template used to generate the syscalls for fuzzing.
question_temp = '''\
Please generate a comprehensive syz program for fuzzing the syscall "%s". Refer to the syscall's synopsis and usage, ensuring valid syntax by considering argument types and values. Account for syscall dependencies and argument dependencies to ensure semantic validity. Craft an effective interaction among as much relevant and different syscalls as possible to delve into deeper Linux kernel states.'''

total_pairs = {}
target_pairs = {}
history_pairs = {}

def add_to_dict(d, k, v):
    if k not in d:
        d[k] = [v]
    elif v not in d[k]:
        d[k].append(v)


def read_prog(prog_path):
    prog_str = ''
    with open(prog_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines:
            if line and line[0] == '#':
                continue
            prog_str += line
    return prog_str.strip()


def extract_from_record(record_path, ignore_single=False):
    valid_list = []
    cnt = 0
    with open(record_path, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if 'Result info' in line:
                break
            cnt += 1
            splits = line.split(',')
            sig = splits[0].split('_')[-1].split('.')[0]
            c1, c2 = int(splits[1]), int(splits[2])
            c_num = int(splits[3])
            if ignore_single == True and c_num == 1:
                continue
            if c2 == 0:
                if c1 > config["min_thres"]:
                    valid_list.append(sig)
            elif c1 > c2:
                valid_list.append(sig)
            else:
                if c1 > config["max_thres"]:
                    valid_list.append(sig)
    return set(valid_list), cnt


def extract_from_outdir(out_dir):
    valid_list = []
    cnt = 0
    for fn in os.listdir(out_dir):
        if 'Total_CoverRecord' in fn:
            continue
        cnt += 1
        size = os.stat(os.path.join(out_dir, fn)).st_size
        if size > 19 * config["min_thres"]:
            sig = fn.split('_')[-1].split('.')[0]
            valid_list.append(sig)
    return set(valid_list), cnt


def extract_pairs_from_prompts_debug(prompt_path):
    hp, tp = {}, {}
    with open(prompt_path, 'r') as f:
        lines = f.readlines()
        prog_start = 0
        syscall, prog_str = '', ''
        for i in range(len(lines)):
            line = lines[i].strip()
            if line == '':
                continue
            if line[:5] == 'User:':
                prog_start = 0
                if syscall != '' and prog_str != '':
                    add_to_dict(hp, syscall, prog_str)
                    add_to_dict(tp, syscall, prog_str)
                    print('[debug] len(prog_str) = %d'%(len(prog_str)))
                    syscall, prog_str = '', ''
                syscall = line.split(' for fuzzing the syscall ')[1].split('.')[0].split('"')[1]                
                continue
            if line[:10] == 'Assistant:':
                prog_start = 1
                continue
            if prog_start == 1:
                prog_str += '%s\n'%line
                continue
            print('exception line:%s'%line)
        if syscall != '' and prog_str != '':
            add_to_dict(tp, syscall, prog_str)
            add_to_dict(tp, syscall, prog_str)
            print('[debug] len(prog_str) = %d'%(len(prog_str)))
    return hp, tp


def extract_pairs_from_prompts(prompt_path):
    global total_pairs, target_pairs, history_pairs
    expected_different_cnt = 0
    with open(prompt_path, 'r') as f:
        lines = f.readlines()
        prog_start = 0
        syscall, prog_str = '', ''
        for i in range(len(lines)):
            line = lines[i].strip()
            if line == '':
                continue
            if line[:5] == 'User:':
                prog_start = 0
                if syscall != '' and prog_str != '':
                    prog_str = prog_str.strip()
                    add_to_dict(history_pairs, syscall, prog_str)
                    add_to_dict(total_pairs, syscall, prog_str)
                    syscall, prog_str = '', ''
                syscall = line.split(' for fuzzing the syscall ')[1].split('.')[0].split('"')[1]                
                continue
            if line[:10] == 'Assistant:':
                prog_start = 1
                continue
            if prog_start == 1:
                prog_str += '%s\n'%line
                continue
        # do not use the prog_str from the prompts, fetch the prog_str from progs dir
        prog_str = prog_str.strip()
        prog_str2 = read_prog(prompt_path.replace('prompts', 'progs'))
        if prog_str != prog_str2:
            # print('[debug] as expected, the target progs are different, use the prog from progs dir')
            prog_str = prog_str2
            expected_different_cnt += 1
        if syscall != '' and prog_str != '':
            add_to_dict(target_pairs, syscall, prog_str)
            add_to_dict(total_pairs, syscall, prog_str)
    print('[debug] expected_different_cnt = %d'%expected_different_cnt)
                
                
def calc_sample_num(n):
    thres = config['min_sample_thres_per_syscall']
    if n < thres:
        return min(n, config['max_sample_per_syscall'])
    else:
        return min(int(sqrt(n)), config['max_sample_per_syscall'])


def sample_progs(prog_list, n, thres=1000):
    unsort_prog = {}
    sampled_progs = []
    legal_cnt = 0
    for p in prog_list:
        unsort_prog[p] = len(p)
    sorted_progs = sorted(unsort_prog.items(), key=lambda x: x[1], reverse=False)
    for _, l in sorted_progs:
        if l > thres:
            break
        legal_cnt += 1
    if legal_cnt <= n:
        for i in range(legal_cnt):
            sampled_progs.append(sorted_progs[i][0])
        return sampled_progs
    delta = legal_cnt / n
    for i in range(n):
        sampled_progs.append(sorted_progs[int(i*delta)][0])
    return sampled_progs


def split_dataset(dataset):
    train_dataset, eval_dataset = {}, {}
    total_progs = 0
    train_cnt = 0
    eval_cnt = 0
    for k in dataset:
        l = len(dataset[k])
        total_progs += l
        if l <= 1:
            train_dataset[k] = dataset[k]
            train_cnt += 1
        else:
            r = randint(0, l-1)
            train_dataset[k], eval_dataset[k] = [], []
            for i in range(l):
                if i == r:
                    eval_dataset[k].append(dataset[k][i])
                    eval_cnt += 1
                else:
                    train_dataset[k].append(dataset[k][i])
                    train_cnt += 1
    print('[split_dataset] %d train, %d eval, train_rate=%.2f'%(train_cnt, eval_cnt, train_cnt/total_progs*100))
    return train_dataset, eval_dataset


def write_jsonl(jsonl_path, data):
    with open(jsonl_path, 'w') as f:
        for k in data:
            for p in data[k]:
                d = {
                    "context": '',
                    "question": k,
                    "answer": p
                }
                f.write(json.dumps(d)+'\n')
    print('[success] write %s done'%jsonl_path)


if __name__ == '__main__':
    t0 = time()
    parser = argparse.ArgumentParser(description='extract semantic valid progs')
    parser.add_argument('-i', '--semantic_outs', type=str, nargs='+', help='semantic check out dirs or records')
    parser.add_argument('-d', '--merged_dir', type=str, help='merged dir for progs and prompts')
    parser.add_argument('-m', '--min_thres', type=int, help='min threshold')
    parser.add_argument('-M', '--max_thres', type=int, help='max threshold')
    parser.add_argument('-S', '--split_method', type=int, default=0, help='split dataset method 0, 1 (default 0)')
    parser.add_argument('-s', '--ignore_single', action='store_true', help='ignore progs with only one syscall')
    parser.add_argument('-o', '--out', type=str, help='nothing here')
    
    args = parser.parse_args()
    
    if args.min_thres:
        config['min_thres'] = args.min_thres
    if args.max_thres:
        config['max_thres'] = args.max_thres
    print('[debug] min_thres=%d, max_thres=%d'%(config['min_thres'], config['max_thres']))
    
    extracted = set()
    total = 0
    for o in args.semantic_outs:
        if os.path.isfile(o):
            valid, cnt = extract_from_record(o, args.ignore_single)
        elif os.path.isdir(o):
            valid, cnt = extract_from_outdir(o)
        extracted |= valid
        total += cnt
        print('[success] extract %d valid progs from %d in %s'%(len(valid), cnt, o))
    print('[info] In total, extract %d valid progs from %d'%(len(extracted), total))
    
    if args.merged_dir:
        prog_dir = os.path.join(args.merged_dir, 'progs')
        prompt_dir = os.path.join(args.merged_dir, 'prompts')
        assert(len(os.listdir(prog_dir)) == len(os.listdir(prompt_dir)))
        find = 0
        print('[processing] please wait for extract_pairs for %d valid candidates...'%len(extracted))
        for i, fn in enumerate(extracted):                
            prompt_path = os.path.join(prompt_dir, fn)
            if os.path.isfile(prompt_path):
                find += 1                    
                extract_pairs_from_prompts(prompt_path)
        print('[%.2fs] In merged dir, %d of %d are found'%(time()-t0, find, len(extracted)))
        print('[%.2fs] len(target_pairs)=%d, len(history_pairs)=%d, len(total_pairs)=%d'%(time()-t0, len(target_pairs), len(history_pairs), len(total_pairs)))
        
        total_progs = 0
        sample_cnt, should_sample_cnt = 0, 0
        max_prog_len, avg_prog_len = 0, 0
        max_prog_str = ''
        d_len = {'1-100':0, '101-200':0, '201-300':0, '301-500':0, '501-1000':0, '1001-2000':0, '2001-5000':0, '5001-11000':0, '>11000':0}
        print_once = {'1-100':0, '101-200':0, '201-300':0, '301-500':0, '501-1000':1, '1001-2000':1, '2001-5000':1, '5001-11000':1, '>11000':0}
        # stat EnabledCalls
        with open('EnabledCalls', 'r') as f:
            enabled = [line.strip() for line in f.readlines()]
        d_stat = {'disabled':[], 'miss': []}
        
        dataset = {}
        max_sample_num = 0
        for k in total_pairs:
            l = len(total_pairs[k])
            sample_num = calc_sample_num(l)
            should_sample_cnt += sample_num
            max_sample_num = max(max_sample_num, sample_num)
            total_progs += l
            
            sampled_progs = sample_progs(total_pairs[k], sample_num)
            if sample_num != []:
                dataset[question_temp%k] = sampled_progs
            else:
                print('[debug] %d has emplty sampled_progs, len(total_pairs[k]=%d)'%(k, len(total_pairs[k])))
            sample_cnt += len(sampled_progs)
            
            if k in enabled:
                if k not in d_stat:
                    d_stat[k] = l
                else:
                    print('[debug] error, duplicated key: %s'%k)
            else:
                d_stat['disabled'].append(k)
            for p in total_pairs[k]:
                pl = len(p)
                if pl > max_prog_len:
                    max_prog_len = pl
                    max_prog_str = p
                if pl <= 100:
                    d_len['1-100'] += 1
                elif pl <= 200:
                    d_len['101-200'] += 1
                elif pl <= 300:
                    d_len['201-300'] += 1
                elif pl <= 500:
                    d_len['301-500'] += 1
                elif pl <= 1000:
                    d_len['501-1000'] += 1
                elif pl <= 2000:
                    d_len['1001-2000'] += 1
                elif pl <= 5000:
                    d_len['2001-5000'] += 1
                elif pl <= 11000:
                    d_len['5001-11000'] += 1
                else:
                    d_len['>11000'] += 1
                avg_prog_len += pl
                    
        print('[%.2fs] %d progs extracted from prompt files, %d progs should be sampled, %d are sampled'%(time()-t0, total_progs, should_sample_cnt, sample_cnt))
        print('[debug] max_prog_len=%d, avg_prog_len=%.2f, max_sample_num=%d'%(max_prog_len, avg_prog_len/total_progs, max_sample_num))
        # for k in d_len:
        #     print('%s: %d'%(k, d_len[k]))
        
        write_jsonl('dataset.jsonl', dataset)
        if args.split_method == 0:
            train_num = len(dataset) * 0.2
            write_jsonl('train_dataset.jsonl', dataset[:train_num])
            write_jsonl('eval_dataset.jsonl', dataset[train_num:])
        elif args.split_method == 1:
            train_dataset, eval_dataset = split_dataset(dataset)
            write_jsonl('train_dataset.jsonl', train_dataset)
            write_jsonl('eval_dataset.jsonl', eval_dataset)
            
        
        for k in enabled:
            if k not in total_pairs:
                if k not in d_stat['miss']:
                    d_stat['miss'].append(k)
        print('[info] %d syscalls of are disabled, %d syscalls of are missed'%(len(d_stat['disabled']), len(d_stat['miss'])))
        
        with open('dataset_stat.json', 'w') as f:
            json.dump(d_stat, f, indent=4)
        
    print('[%.2fs] Done!'%(time()-t0))
        