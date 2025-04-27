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
from extractor.extractor_prompts import *
try:
    from private_config import *
except ImportError:
    from config import *


def extract_outputs(response_text, syscall, out_dir, tag, method):
    response_text = response_text.strip()
    if method == 1:
        dir_path = os.path.join(out_dir, tag)
        check_dir(dir_path)
        with open(os.path.join(dir_path, '%s_response'%syscall), 'w', encoding='utf-8') as f:
            f.write("%s"%response_text)
    elif method == 2:
        dir_path = os.path.join(out_dir, tag)
        check_dir(dir_path)
        with open(os.path.join(dir_path, '%s.json'%syscall), 'w', encoding='utf-8') as f:
            json.dump(response_text, f, indent=4)


def condense_text(text, dumb=True):
    msg_with_hist = [{"role": "system", "content": SYSTEM_PROMPT_CONDENSE}]

    query = 'According to the demand of how to condense text described in system prompt, condense the following text: "%s". Output the condensed text without any other words.'%text
    simp_result, _ = query_with_history(msg_with_hist, query, LLM_MODEL, dumb)

    return simp_result


def format_gen_results(syscall, gen_results, dumb=True):
    msg_with_hist = [{"role": "system", "content": "You are an expert of Natural Language Processing and Linux Kernel"}]
    query = 'Extract the information from the following text and identify the system calls which "%s()" explicitly depend and implicitly depend on, and also generate the system calls which "%s()" is explicitly depended and implicitly depended upon: "%s". The output MUST strictly follow the format: "explicit depend: xxx \n implicit depend: xxx \n explicit depended: xxx \n implicit depended: xxx \n", where "xxx" represents the names of system calls, and "xxx" must not include "%s()" itself. If there are multiple system calls in the result, separate them with ", ". If there are no dependencies, replace "xxx" with "null". '%(syscall, syscall, gen_results, syscall)
    format_result, _ = query_with_history(msg_with_hist, query, LLM_MODEL, dumb)
    
    return format_result


def lines2result(lines, builtin_syscall_list):
    output_lines = []

    flag1 = False
    flag2 = False
    flag3 = False
    flag4 = False
    final_flag = False

    explicit_depend = "explicit depend: null"
    implicit_depend = "implicit depend: null"
    explicit_depended = "explicit depended: null"
    implicit_depended = "implicit depended: null"
        
    for line in lines[::-1]:
        if line.find("explicit depend: ")!=-1 and flag1 == False:    
            cleaned_line = re.sub(r'\([^)]*\)', '', line[line.find("explicit depend: ")+len("explicit depend: ")-1:])
            items = [item.strip() for item in cleaned_line.split(',')]
            filtered_items = [item for item in items if item in builtin_syscall_list]
            checked_result = ', '.join(filtered_items)
            if checked_result != "" :
                flag1 = True
                explicit_depend = "explicit depend: "+checked_result

        elif line.find("implicit depend: ")!=-1 and flag2 == False:
            cleaned_line = re.sub(r'\([^)]*\)', '', line[line.find("implicit depend: ")+len("implicit depend: ")-1:])
            items = [item.strip() for item in cleaned_line.split(',')]
            filtered_items = [item for item in items if item in builtin_syscall_list]
            checked_result = ', '.join(filtered_items)
            if checked_result != "" :
                flag2 = True
                implicit_depend = "implicit depend: "+checked_result

        elif line.find("explicit depended: ")!=-1 and flag3 == False:
            cleaned_line = re.sub(r'\([^)]*\)', '', line[line.find("explicit depended: ")+len("explicit depended: ")-1:])
            items = [item.strip() for item in cleaned_line.split(',')]
            filtered_items = [item for item in items if item in builtin_syscall_list]
            checked_result = ', '.join(filtered_items)
            if checked_result != "" :
                flag3 = True
                explicit_depended = "explicit depended: "+checked_result

        elif line.find("implicit depended: ")!=-1 and flag4 == False:
            cleaned_line = re.sub(r'\([^)]*\)', '', line[line.find("implicit depended: ")+len("implicit depended: ")-1:])
            items = [item.strip() for item in cleaned_line.split(',')]
            filtered_items = [item for item in items if item in builtin_syscall_list]
            checked_result = ', '.join(filtered_items)
            if checked_result != "" :
                flag4 = True
                implicit_depended = "implicit depended: "+checked_result

    output_lines.append(explicit_depend)
    output_lines.append(implicit_depend)
    output_lines.append(explicit_depended)
    output_lines.append(implicit_depended)

    if flag1 == False and flag2 == False and flag3 == False and flag4 == False:
        final_flag = False
    else:
        final_flag = True
    
    return(output_lines, final_flag)


def generate_step_by_step(syscall, append_tag='', dumb=False):
    tag = 'syscall_dependencies_%s'%append_tag
    ret = {
        'tag': tag,
        'results':''
    }
    if check_exist(syscall, OUT_DIR, tag) == True:
        logger.info('syscall %s already generated'%syscall)
        return ret

    msg_with_hist1 = [{"role": "system", "content": SYSTEM_PROMPT_GENERATE}]
    
    # built in syscall list for compare
    builtin_syscall_list = []
    with open('../data/builtin_syscalls.txt', 'r') as file:
        for line in file:
            builtin_syscall_list.append(line.strip())
    
    # from docs read "syscallname.json"
    path = '../crawler/man_docs/'
    file = syscall + '.json'
    file_path = path + file
    gen_results = ""
    gen_results_part2 = ""

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            syscall_info = json.load(f)
            syscall_synopsis = syscall_info["SYNOPSIS"]
            syscall_description = syscall_info["DESCRIPTION"]
            syscall_notes = ""
            try:
                syscall_notes = syscall_info["NOTES"]
            except:
                pass
            
            # gen result 1. If all items are "null", then gen again. max try: 3 
            loop_max_gen1 = 3
            for i in range(loop_max_gen1):
                simplified_description = condense_text(syscall_description, dumb)
                simplified_notes = condense_text(syscall_notes, dumb)
                query = QUERY_GENERATE(syscall, syscall_synopsis, simplified_description, simplified_notes)
                msg_with_hist_temp = msg_with_hist1
                first_results, _ = query_with_history(msg_with_hist_temp, query, dumb)
                gen_results = first_results.lower()
                second_results = format_gen_results(syscall, gen_results, dumb)
                gen_results_part2 = second_results.lower()
                gen_results = gen_results +'\n'+ gen_results_part2
                lines = gen_results_part2.splitlines()

                info_dict1 = {}
                output_lines, flag = lines2result(lines, builtin_syscall_list)
                all_null_warning = "warning: all results null, please check gen_results(gpt response)"
                if flag == False:
                    output_lines.append(all_null_warning)
                else:
                    gen_results = '\n' + "gen1 succeed in the %d time"%i + gen_results
                    break
            
            gen1_result = ""
            for line in output_lines:
                gen1_result = gen1_result + line
                key, value = line.split(':', 1)
                info_dict1[key.strip()] = value.strip()
            extract_outputs(info_dict1, syscall, OUT_DIR, tag+'_gen1', 2)
            
            # gen result 2. this result is more creative than 1. use gpt's kmowledge to gen and revise
            # If all items are "null", then gen again. max try: 2
            msg_with_hist2 = [{"role": "system", "content": SYSTEM_PROMPT_FREE_GEN_FROM_LIST}]         
            query = QUERY_FREE_GEN(syscall, gen1_result)
            loop_max_gen2 = 2
            for i in range(loop_max_gen2):
                msg_with_hist_temp = msg_with_hist2
                first_results, _ = query_with_history(msg_with_hist_temp, query, dumb)
                creative_results = first_results.lower()
                second_results = format_gen_results(syscall, creative_results, dumb).lower()
                lines = second_results.splitlines()

                info_dict2 = {}
                output_lines2, flag = lines2result(lines, builtin_syscall_list)
                all_null_warning = "warning: all results null, please check gen_results(gpt response)"
                if flag == False:
                    output_lines2.append(all_null_warning)
                else:
                    gen_results = gen_results + '\n' + "gen2 succeed in the %d time"%i
                    break
            
            gen_results = gen_results + creative_results
            for line in output_lines2:
                key, value = line.split(':', 1)
                info_dict2[key.strip()] = value.strip()

            extract_outputs(info_dict2, syscall, OUT_DIR, tag+'_gen2', 2)
    
    except Exception as e:
        logger.exception('Exception occured: %s'%e)

    # save gpt responses
    try:
        extract_outputs(gen_results, syscall, OUT_DIR, tag, 1)
    except Exception as e:
        logger.exception('Exception occured: %s'%e)

    ret['results'] = gen_results
    return ret


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dependency Extractor')
    parser.add_argument('-p', '--proxy_check', action='store_true', help='check proxy')
    parser.add_argument('-f', '--file', type=str, default='../crawler/syscall_from_manpage.txt', help='syscall list file')
    parser.add_argument('-S', '--sample_step', type=int, help='sample syscall from file every S steps')
    parser.add_argument('-k', '--api_key', type=str, help='manually specified api key')
    parser.add_argument('-c', '--calls', type=str, nargs='+', help='manually specified call lists')
    parser.add_argument('-t', '--append_tag', type=str, default='', help='append tag to differ the corpus dir')
    parser.add_argument('-d', '--dumb', action='store_true', help='dumb mode')
    args = parser.parse_args()
    
    check_dir(LOG_DIR)
    log_name = time.strftime("dependency_extractor_%Y-%m-%d.log", time.localtime())
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

    if args.proxy_check == True:
        check_proxy(proxies)
    else:
        call_cnt = 0
        for i, call in enumerate(call_list):
            if args.sample_step and i % args.sample_step != 0:
                continue
            if call_cnt % 20 == 19:
                sleep(180)
            logger.debug('Extracting dependencies for syscall %s'%call)
            ret = generate_step_by_step(call, args.append_tag, args.dumb)
            call_cnt += 1