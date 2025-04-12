import argparse
import shutil
import os
from time import time

t0 = time()


def print_t(s, t):
    print('[%.2fs] %s'%(time()-t, s))


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


def diff_fns(fn_list1, fn_list2, d1, d2):
    common_cnt = 0
    for fn in fn_list1:
        if fn in fn_list2:
            common_cnt += 1
    print_t('diff results:\nlen(%s)=%d\nlen(%s)=%d\ncommon_cnt=%d'%(d1, len(fn_list1), d2, len(fn_list2), common_cnt), t0)
    return common_cnt


def merge_progs(out_dir, d_list, fn_list):
    assert(len(d_list) == len(fn_list))
    total_progs = 0
    merged_fns = []
    merged_fpaths = []
    for i in range(len(d_list)):
        for fn in fn_list[i]:
            if fn not in merged_fns:
                src_path = os.path.join(d_list[i], fn)
                dst_path = os.path.join(out_dir, fn)
                shutil.copy(src_path, dst_path)
                merged_fns.append(fn)
                merged_fpaths.append(os.path.join(d_list[i], fn))
        total_progs += len(fn_list[i])
        print_t('done for copy %d progs in %s'%(len(fn_list[i]), d_list[i]), t0)
    print_t('total_progs = %d, merged_progs = %d, common_progs = %d'%(total_progs, len(os.listdir(out_dir)), total_progs-len(os.listdir(out_dir))), t0)
    return merged_fns, merged_fpaths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='diff generated programs')
    parser.add_argument('-d', '--fuzzer_out_dirs', type=str, nargs='+', help='dirs of the generated programs')
    parser.add_argument('-o', '--out', type=str, help='create a dir and merge the generated programs to the dir')

    args = parser.parse_args()
    
    print_t('get args', t0)
    assert(args.fuzzer_out_dirs)
    out_dirs = list(args.fuzzer_out_dirs)
    prog_d_list = [os.path.join(d, 'generated_corpus') for d in out_dirs]
    prompt_d_list = [os.path.join(d, 'query_prompts') for d in out_dirs]
    fn_list = [os.listdir(d) for d in prog_d_list]
    
    if len(prog_d_list) == 2:
        diff_fns(fn_list[0], fn_list[1], prog_d_list[0], prog_d_list[1])
    elif len(prog_d_list) > 2:
        for i in range(1, len(prog_d_list)):
            diff_fns(fn_list[0], fn_list[i], prog_d_list[0], prog_d_list[i])
    
    if args.out:
        out_prog_dir = os.path.join(args.out, 'progs')
        out_prompt_dir = os.path.join(args.out, 'prompts')
        check_dir(out_prog_dir)
        check_dir(out_prompt_dir)
        _, merged_fpaths = merge_progs(out_prog_dir, prog_d_list, fn_list)
        for fpath in merged_fpaths:
            prog_dir = os.path.dirname(fpath)
            fn = os.path.basename(fpath)
            prompt_dir = prog_dir.replace('generated_corpus', 'query_prompts')
            shutil.copy(os.path.join(prompt_dir, '%s_1'%fn), os.path.join(out_prompt_dir, fn))
        print_t('query prompts copy done', t0)
        
    
    
