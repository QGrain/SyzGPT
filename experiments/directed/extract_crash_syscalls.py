import argparse
import os

def get_args():
    parser = argparse.ArgumentParser(description='Extract crash syscalls from a poc file')
    parser.add_argument('-i', '--input_poc', type=str, required=True, help='Path of the poc file')
    parser.add_argument('-o', '--output_syscalls', type=str, required=True, help='Output file path')
    args = parser.parse_args()
    return args

def extract_syscalls(input_file):
    syscalls = []
    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                continue

            open_paren_index = line.find('(')
            if open_paren_index == -1:
                continue  # Skip lines without '('
            # Check for '=' before the '('
            equal_index = line.rfind('=', 0, open_paren_index)
            if equal_index != -1:  # '=' exists before '('
                syscall = line[equal_index + 1:open_paren_index].strip()
            else:  # No '=' found
                syscall = line[:open_paren_index].strip()

            if syscall != '' and syscall not in syscalls:
                syscalls.append(syscall)

    return syscalls 

def write_syscalls(output_file, syscalls):
    with open(output_file, 'w') as f:
        for syscall in syscalls:
            f.write(f"{syscall}\n")

if __name__ == '__main__':
    args = get_args()
    # Ensure input file exists
    if not os.path.isfile(args.input_poc):
        raise FileNotFoundError(f"Input file {args.input_poc} does not exist.")

    # Extract syscalls and write to output
    unique_syscalls = extract_syscalls(args.input_poc)
    write_syscalls(args.output_syscalls, unique_syscalls)