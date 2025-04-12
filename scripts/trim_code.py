import sys

def remove_comments_and_blank_lines(input_file, output_file, comment_char):
    with open(input_file, 'r', encoding='utf-8') as f_in:
        lines = f_in.readlines()

    # remove comments and blank lines
    lines = [line for line in lines if not line.strip().startswith(comment_char) and line.strip() != '']

    with open(output_file, 'w', encoding='utf-8') as f_out:
        f_out.writelines(lines)

if __name__ == '__main__':
    remove_comments_and_blank_lines(sys.argv[1], sys.argv[2], '#')