import json
import os
import argparse
from time import time


def get_args():
    parser = argparse.ArgumentParser(description='Merge syscall dependencies')
    parser.add_argument('-d', '--gen_dir', type=str, nargs='+', help='directories to dependencies gen1 and gen2')
    parser.add_argument('-o', '--out_dir', type=str, help='write merge result to out_dir, default ./call_dependencies/')

    args = parser.parse_args()
    return args


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


def read_depend(path):
    with open(path, 'r') as f:
        d = json.load(f)
    return d


def write_depend(d, path):
    with open(path, 'w') as f:
        json.dump(d, f, indent=4)


def combine_explicit_implicit(d):
    new_d = {
        "depend": set(),
        "depended": set()
    }
    if d["explicit depend"] != "null":
        new_d["depend"] = new_d["depend"] | set(d["explicit depend"].split(', '))
    if d["implicit depend"] != "null":
        new_d["depend"] = new_d["depend"] | set(d["implicit depend"].split(', '))
    if d["explicit depended"] != "null":
        new_d["depended"] = new_d["depended"] | set(d["explicit depended"].split(', '))
    if d["implicit depended"] != "null":
        new_d["depended"] = new_d["depended"] | set(d["implicit depended"].split(', '))
    return new_d


def combine_depends(d1, d2):
    new_d = {
        "depend": set(),
        "depended": set()
    }
    for k in d1:
        new_d[k] = new_d[k] | d1[k]
        new_d[k] = new_d[k] | d2[k]
    new_d["depend"] = list(new_d["depend"])
    new_d["depended"] = list(new_d["depended"])
    return new_d


if __name__ == '__main__':
    t0 = time()
    
    args = get_args()

    # gen1 = './syscall_dependencies_final_gen1'
    # gen2 = './syscall_dependencies_final_gen2'
    # comb = './call_dependencies_combine'
    assert(len(args.gen_dir) == 2)
    gen1, gen2 = args.gen_dir[0], args.gen_dir[1]
    comb = args.out_dir or './call_dependencies'
    check_dir(comb)

    for fn in os.listdir(gen1):
        # print('[+] proccessing: %s'%fn)
        d1 = read_depend(os.path.join(gen1, fn))
        nd1 = combine_explicit_implicit(d1)
        
        d2 = read_depend(os.path.join(gen2, fn))
        nd2 = combine_explicit_implicit(d2)
        
        d_comb = combine_depends(nd1, nd2)
        if d_comb["depend"] == [] and d_comb["depended"] == []:
            print('[x] %s is none!'%fn)
        write_depend(d_comb, os.path.join(comb, fn))

    print('Done! Cost %.2fs'%(time()-t0))