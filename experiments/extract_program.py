import argparse
import os


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


def extract_program_content1(response_text):
    prog_content = ''
    prog_start = 0
    for line in response_text.split('\n'):
        line = line.strip()
        if line == '' or line[0] == '#':
            continue
        if '(' in line or ')' in line:
                if prog_start == 0:
                    prog_start = 1
                prog_content += '%s\n'%line
        elif prog_start == 1:
            break
        if line[:5] == 'User:':
            break
    return prog_content


def extract_from_file(raw_path, dst_path='', syscall=''):
    with open(raw_path, 'r') as f:
        raw_text = f.read()
    prog_content = extract_program_content1(raw_text)
    if syscall != '' and syscall not in prog_content:
        return ''
    if prog_content != '' and dst_path != '' and dst_path != None:
        with open(dst_path, 'w') as f:
            f.write(prog_content)
    return prog_content


def extract_from_dir(src_dir, dst_dir='', check_contain=True):
    success = 0
    for fn in os.listdir(src_dir):
        dst_path = ''
        if dst_dir != '' and dst_dir != None:
            dst_path = os.path.join(dst_dir, fn)
        if check_contain == True:
            prog_content = extract_from_file(os.path.join(src_dir, fn), dst_path, '%s('%fn)
        else:
            prog_content = extract_from_file(os.path.join(src_dir, fn), dst_path)
        if prog_content != '':
            success += 1
    print('%d/%d are successfully extracted'%(success, len(os.listdir(src_dir))))
    


if __name__ == '__main__':
    parser = argparse.ArgumentParser('extract program from raw LLM outputs')
    parser.add_argument('--src_dir', type=str, help='path to src_dir')
    parser.add_argument('--dst_dir', type=str, help='path to dst_dir')
    parser.add_argument('--check_contain', action='store_true', help='enable containing check')
    args = parser.parse_args()
    
    if args.dst_dir:
        check_dir(args.dst_dir)
    extract_from_dir(args.src_dir, args.dst_dir, args.check_contain)