import os
import argparse
from typing import List

def get_strict_max_prefix_lines(syz_dir: str) -> int:
    files = []
    for filename in os.listdir(syz_dir):
        if filename.endswith('.trace0'):  # suppose the suffix of the trace file is .trace0
            with open(os.path.join(syz_dir, filename), 'r') as f:
                lines = f.readlines()
                files.append(lines)
    
    if not files:
        return 0
    
    # get the length of the shortest file, because the maximum same prefix cannot exceed the length of the shortest file
    min_length = min(len(file) for file in files)
    
    # compare each line of all files
    strict_max_prefix_lines = 0
    for i in range(min_length):
        current_line = files[0][i]
        # check if all files have the same line at the i-th position
        if all(file[i] == current_line for file in files):
            strict_max_prefix_lines += 1
        else:
            break
            
    return strict_max_prefix_lines


def search_avg_max_prefix_lines(syz_dir: str, verbose: bool = False) -> dict:
    avg_max_prefix_lines = 0
    for n in range(1, 100):
        prefix_groups = count_n_prefix_groups(syz_dir, n, verbose)
        try:
            cur_max_prefix_lines = n * (prefix_groups[0][1] / len(os.listdir(syz_dir)))
            if cur_max_prefix_lines >= avg_max_prefix_lines:
                avg_max_prefix_lines = cur_max_prefix_lines
            else:
                break
        except:
            break
    return avg_max_prefix_lines
    

def count_n_prefix_groups(syz_dir: str, n: int, verbose: bool = False) -> dict:
    # use a dictionary to store the mapping from the first N lines to the number of files
    prefix_groups = {}
    less_count = 0  # count the number of files with length less than N
    total_count = len(os.listdir(syz_dir))
    
    for filename in os.listdir(syz_dir):
        if filename.endswith('.trace0'):
            with open(os.path.join(syz_dir, filename), 'r') as f:
                lines = f.readlines()
                if len(lines) < n:
                    less_count += 1
                    continue
                    
                # use the first N lines as the key
                prefix = tuple(lines[:n])
                prefix_groups[prefix] = prefix_groups.get(prefix, 0) + 1
    
    # sort the groups by the number of files in descending order
    sorted_groups = sorted(prefix_groups.items(), key=lambda x: x[1], reverse=True)
    
    if verbose:
        print(f"\nNumber of file less than N lines: {less_count}")
        print(f"Number of different prefix groups: {len(prefix_groups)}")
        print("\nGroup size distribution:")
        for prefix, count in sorted_groups:
            print(f"Number of files: {count}")
            print("Content:")
            for line in prefix:
                print(f"    {line.strip()}")
            print("---")
    
    return sorted_groups


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Get the maximum number of same prefix lines in the syz trace files")
    parser.add_argument("-d", "--syz_dir", type=str, required=True)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    
    print(f"Strict max prefix lines: {get_strict_max_prefix_lines(args.syz_dir):.3f}")
    print("---")
    avg_max_prefix_lines = search_avg_max_prefix_lines(args.syz_dir, args.verbose)
    print(f"Average max prefix lines: {avg_max_prefix_lines:.3f}")
