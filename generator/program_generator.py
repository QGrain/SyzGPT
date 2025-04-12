import os
import sys
sys.path.append('..')
import openai
import argparse
import re
import json
import time
from generator.utils import *
from generator.gpt_wrapper import *
try:
    from private_config import *
except ImportError:
    from config import *
from generator.prompts import *


def extract_program_content(response_text):
    '''For the generation results of local LLMs'''
    prog_content = ''
    prog_start = 0
    for line in response_text.split('\n'):
        line = line.strip()
        if line == '':
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


def replace_escapes():
    pass


def extract_programs(response_text, syscall, out_dir, suffix, force_fn=None, filter_for_local=False):
    check_dir(out_dir)
    if filter_for_local == True:
        response_text = extract_program_content(response_text)
    response_text = response_text.strip()
    if force_fn:
        with open(os.path.join(out_dir, force_fn), 'w', encoding='utf-8') as f:
            f.write('%s'%response_text)
        return
    if suffix != '.json':
        new_fn = syscall.replace('$', '_')
        with open(os.path.join(out_dir, '%s%s'%(new_fn, suffix)), 'w', encoding='utf-8') as f:
            f.write('%s'%response_text)
    else:
        with open(os.path.join(out_dir, '%s%s'%(syscall, suffix)), 'w', encoding='utf-8') as f:
            json.dump(response_text, f, indent=4)
            

def replace_unprintables(s):
    new_s = ''
    for c in s:
        if not c.isprintable() and c != chr(0x0a):
            new_s += '\\x{:02x}'.format(ord(c))
        else:
            new_s += c
    return new_s


# Deprecated
def generate_program(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, append_tag='', dumb=True):
    return 0
#     tag = 'programs_%s'%append_tag
#     ret = 0
#     if check_exist(syscall, OUT_DIR, tag) == True:
#         logger.info('syscall %s already generated'%syscall)
#         return ret

#     msg_with_hist1 = [{"role": "system", "content": SYS_PROMPT_SYZ_SYNTAX_SIMP}]
    
#     try:
#         # query = FEWSHOT_QUERY(syscall)
#         query = FEWSHOT_QUERY_WITH_DEPEND(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, 3)
#         response, tks = query_with_history(msg_with_hist1, query, dumb)
#         response = replace_unprintables(response)
#         if dumb == False:
#             print('[Response for %s]\n%s'%(syscall, response))
#         prog_dir = os.path.join(OUT_DIR, tag)
#         extract_programs(response, syscall, prog_dir, '.prog')
#         logger.success('Successfully generate syz program for %s, cost %d tokens'%(syscall, tks))
#         ret = tks
#     except Exception as e:
#         logger.exception('Exception occured: %s'%e)
    
#     return ret
        

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Program Generator')
    parser.add_argument('-p', '--proxy_check', action='store_true', help='check proxy')
    parser.add_argument('-f', '--file', type=str, help='syscall list file')
    parser.add_argument('-S', '--sample_step', type=int, help='sample syscall from file every S steps')
    parser.add_argument('-k', '--api_key', type=str, help='manually specified api key')
    parser.add_argument('-c', '--calls', type=str, nargs='+', help='manually specified call lists')
    parser.add_argument('-t', '--append_tag', type=str, help='append tag to differ the corpus dir')
    parser.add_argument('-v', '--variant_mode', action='store_true', help='variant mode, specify with -c or -f when targets are variants')
    parser.add_argument('-d', '--dumb', action='store_true', help='dumb mode')
    args = parser.parse_args()
    
    check_dir(LOG_DIR)
    log_name = time.strftime("program_generator_%Y-%m-%d.log", time.localtime())
    log_path = os.path.join(LOG_DIR, log_name)
    init_logger(log_file=log_path)

    call_list = []
    if args.calls:
        call_list = list(args.calls)
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                call_list.append(line.split('(2)')[0])

    if args.api_key:
        openai.api_key = args.api_key

    if args.append_tag:
        append_tag = args.append_tag
    else:
        append_tag = ''


    # load syzkaller builtin syscalls
    builtin_syscalls_d = {}
    with open('../data/builtin_syscalls.json', 'r', encoding='utf-8') as f:
        builtin_syscalls_d = json.load(f)
        
    # load call dependencies
    call_depend = {}
    with open('../data/call_dependencies/call_dependencies_all.json', 'r') as f:
        call_depend = json.load(f)
        
    # load syz dependencies
    syz_depend = {}
    with open('../data/syz_dependencies/syz_depend_inout.json', 'r') as f:
        syz_depend = json.load(f)
        
    # load reverse_index
    with open('/root/corpus/enriched-corpus-1106_rev_index.json', 'r') as f:
        reverse_index = json.load(f)


    if args.proxy_check == True:
        check_proxy(proxies)
    else:
        call_cnt = 0
        total_tokens = 0
        if args.variant_mode:
            for i, call_variant in enumerate(call_list):
                if args.sample_step and i % args.sample_step != 0:
                    continue
                if call_cnt % 20 == 19:
                    logger.info('Security 30s sleep every 20 syscalls\' generation.')
                    sleep(30)
                logger.debug('Generating syz program for syscall %s'%(call_variant))
                cost_tokens = generate_program(call_variant, call_depend, syz_depend, builtin_syscalls_d, reverse_index, append_tag, args.dumb)
                total_tokens += cost_tokens
                if cost_tokens > 0:
                    call_cnt += 1
        else:
            for i, call in enumerate(call_list):
                if args.sample_step and i % args.sample_step != 0:
                    continue
                if call not in builtin_syscalls_d:
                    continue
                if call_cnt % 20 == 19:
                    logger.info('Security 30s sleep every 20 syscalls\' generation.')
                    sleep(30)
                for variant in builtin_syscalls_d[call]:
                    call_variant = variant['Name']
                    logger.debug('Generating syz program for syscall %s (%s)'%(call, call_variant))
                    cost_tokens = generate_program(call_variant, call_depend, syz_depend, builtin_syscalls_d, reverse_index, append_tag, args.dumb)
                    total_tokens += cost_tokens
                    if cost_tokens > 0:
                        call_cnt += 1
    logger.success('Finish generation %d call_variants. Cost %d tokens in total.'%(call_cnt, total_tokens))