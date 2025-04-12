import os, random, requests, json
import argparse
import multiprocessing
from time import time


def search_syscall(syzkaller_dir, syscall):
    syzlang_doc_dir = os.path.join(syzkaller_dir, 'sys/linux/')
    doc_fn = []
    for call in syscall:
        escape_call = call.replace('$', '\$')
        grep_cmd = 'grep -r "%s(" %s | grep ".txt:%s("'%(escape_call, syzlang_doc_dir, escape_call)
        p = os.popen(grep_cmd)
        search_res = p.read()
        p.close()
        
        for s in search_res.split('\n'):
            if s == '':
                continue
            fn = os.path.basename(s.split(':%s'%call)[0])
            if fn not in doc_fn:
                # print('s=%s, fn=%s, call=%s'%(s, fn, call), s.split(':%s'%call))
                doc_fn.append(fn)
    return doc_fn


def arg_parse():
    parser = argparse.ArgumentParser('get syzlang documentation')
    parser.add_argument('-s', '--syzkaller', type=str, help='path to syzkaller fuzzer')
    parser.add_argument('-f', '--syscall_list', type=str, help='Path to syscall list file (one syscall each line).')
    parser.add_argument('-c', '--call', type=str, help='Fetch the syzlang doc of the specified system call')
    
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    start_t = time()
    args = arg_parse()
    
    if args.syscall_list:
        # syscall_from_manpage.txt
        with open(args.syscall_list, 'r', encoding='utf-8') as f:
            systemcall_list = f.readlines()
    elif args.call:
        systemcall_list = [args.call]
    else:
        print('[ERROR] You must specify -f or -c')
        exit(1)
        
    with open('../data/builtin_syscalls.json', 'r', encoding='utf-8') as f:
        builtin_syscalls = json.load(f)
    
    notin_cnt, none_cnt, success_cnt, cnt = 0, 0, 0, 0
    for line in systemcall_list:
        call = line.strip()
        if call not in builtin_syscalls:
            notin_cnt += 1
            continue
        cnt += 1
        spec_call_list = [d["Name"] for d in builtin_syscalls[call]]
        doc_fn = search_syscall(args.syzkaller, spec_call_list)
        
        if len(doc_fn) == 0:
            print('[%d][%.3fs][Exception][%s] doc_fn = []'%(cnt, time()-start_t, call))
            none_cnt += 1
        else:
            print('[%d][%.3fs][Done][%s] doc_fn ='%(cnt, time()-start_t, call), doc_fn)
            success_cnt += 1
    print('not in builtin: %d, no doc: %d, success: %d, total: %d'%(notin_cnt, none_cnt, success_cnt, none_cnt+success_cnt))