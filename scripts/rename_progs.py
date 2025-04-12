import os
import argparse
import hashlib
import binascii
import shutil
from time import time


def calc_hash(path):
    with open(path, 'rb') as f:
        byte_data = f.read()
    h = hashlib.sha1(byte_data)
    return binascii.hexlify(h.digest()).decode('utf-8')


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='rename the progs with hash string')
    parser.add_argument('in_path', type=str, help='input path of prog dir or prog')
    parser.add_argument('-o', '--out_dir', type=str, help='output dir for renamed progs')
    args = parser.parse_args()
    
    t0 = time()
    
    if os.path.isdir(args.in_path):
        is_dir = 1
        tmp_dir = args.in_path
        if tmp_dir[-1] == '/':
            tmp_dir = tmp_dir[:-1] + '_rename'
        out_dir = args.out_dir or tmp_dir
        check_dir(out_dir)
        for fn in os.listdir(args.in_path):
            in_file = os.path.join(args.in_path, fn)
            sig = calc_hash(in_file)
            out_file = os.path.join(out_dir, sig)
            shutil.copyfile(in_file, out_file)
    else:
        is_dir = 0
        sig = calc_hash(args.in_path)
        print('[+] sig of %s: %s'%(args.in_path, sig))

    print('[Done] Cost %.2fs'%(time()-t0))
    