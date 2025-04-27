import os
import sys
import argparse

def reverse_prog(file_path, out_dir=None):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        reversed_lines = [line.strip() + '\n' for line in lines[::-1]]
    
    if out_dir is None:
        out_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    out_path = os.path.join(out_dir, file_name + '.rev')
    with open(out_path, 'w') as f:
        f.writelines(reversed_lines)

def reverse_progs_in_dir(dir_path, out_dir=None):
    if out_dir is None:
        out_dir = dir_path
    os.makedirs(out_dir, exist_ok=True)
    for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        if os.path.isfile(file_path):
            reverse_prog(file_path, out_dir)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Reverse the programs in a directory.")
    parser.add_argument('dir_path', type=str, help='Path to the directory containing the progs to reverse')
    parser.add_argument('-o', '--out_dir', type=str, help='Output directory for reversed progs (optional)')
    args = parser.parse_args()
    
    if os.path.isdir(args.dir_path):
        reverse_progs_in_dir(args.dir_path, args.out_dir)
        print("Progs Reversing Process Done!")
    else:
        print("Please specify a valid dir path!")