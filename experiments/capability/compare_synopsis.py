import os
import json
import re
from difflib import SequenceMatcher
from math import sqrt

# start_symbols = ['unsigned', 'signed', 'char', 'int', 'long', 'float', 'double', 'void', 'bool', '[[deprecated]]', 'ssize_t']
# end_symbols = [';']

def load_synopsis_from_man(man_path):
    with open(man_path, 'r') as f:
        man_doc = json.load(f)
    
    try:
        synopsis = man_doc['SYNOPSIS']
    except:
        synopsis = ''
    return synopsis


def load_synopsis_from_llm(synop_path):
    with open(synop_path, 'r') as f:
        synopsis = f.read()
    return synopsis


def synopsis2list(synopsis):
    lines = synopsis.split('\n')
    l = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.endswith(","):
            combined_lines = [line]
            i += 1
            combined_lines.append(lines[i].strip())

            while i < len(lines) and lines[i].strip().endswith(","):
                i += 1
                combined_lines.append(lines[i].strip())

            combined_line = " ".join(combined_lines)
            i += 1
            l.append(combined_line)
        else:
            l.append(line)
            i += 1

    return l


def filter_lines(syscall, lines):
    include_lines = []
    declare_lines = []

    for line in lines:
        if line.startswith("#include"):
            match = re.match(r'#include\s*(<.*?>)', line)
            if match:
                if match.group(0) not in include_lines:
                    include_lines.append(match.group(0))
        else:
            line = re.sub(r'\[\[deprecated\]\]', '', line).strip()
            line = re.sub(r'\[\[noreturn\]\]', '', line).strip()
            left_parenthesis = line.find("(")
            right_parenthesis = line.rfind(")")
            if left_parenthesis != -1 and right_parenthesis != -1 and left_parenthesis < right_parenthesis and right_parenthesis != len(line)-1 and line[right_parenthesis+1] == ';':
                if line not in declare_lines:
                    declare_lines.append(line)

    syscall_matched = 0
    for declare in declare_lines:
        left_parenthesis = declare.find("(")
        right_parenthesis = declare.rfind(")")

        fuc_type_name = declare[:left_parenthesis].strip()
        fuc_name = fuc_type_name.split()[-1]
        if fuc_name == syscall:
            syscall_matched = 1
            declare_lines = [declare]
            break

    if syscall_matched == 0:
        max_similarity = 0
        sim_declare = ''
        for declare in declare_lines:
            left_parenthesis = declare.find("(")
            right_parenthesis = declare.rfind(")")

            fuc_type_name = declare[:left_parenthesis].strip()
            fuc_name = fuc_type_name.split()[-1]
            if calc_str_similarity(syscall, fuc_name) > max_similarity:
                max_similarity = calc_str_similarity(syscall, fuc_name)
                sim_declare = declare
        if sim_declare:
            declare_lines = [sim_declare]
    return include_lines, declare_lines


def parse_args(lst):
    modified_lst = []
    args_dict = []

    # remove _Nullable
    for item in lst:
        modified_item = item

        if '_Nullable' in item:
            nullable_index = item.find('_Nullable')
            
            non_space_index = nullable_index + len('_Nullable')
            while non_space_index < len(item) and item[non_space_index] == ' ':
                non_space_index += 1
            
            modified_item = item[:nullable_index] + item[non_space_index:]
        if 'restrict' in modified_item:
            # find '_Nullable'
            nullable_index = modified_item.find('restrict')
            
            # find next non-blank
            non_space_index = nullable_index + len('restrict')
            while non_space_index < len(modified_item) and modified_item[non_space_index] == ' ':
                non_space_index += 1
            
            # remove '_Nullable' to next blank
            modified_item = modified_item[:nullable_index] + modified_item[non_space_index:]
            
        if modified_item.strip() != '':
            modified_lst.append(modified_item.strip())  # remove blank

    # generate dict
    for item in modified_lst:
        if '(' in item:
            left_parenthesis_index = item.find('(')
            
            space_before_left_parenthesis = item.rfind(' ', 0, left_parenthesis_index)
            arg_name = item[space_before_left_parenthesis + 1:]

            arg_type = item[:space_before_left_parenthesis].strip()
        else:
            last_space_index = item.rfind(' ')
            arg_name = item[last_space_index + 1:]
            arg_type = item[:last_space_index].strip()

        args_dict.append([arg_name, arg_type])

    return modified_lst, args_dict


def calc_str_similarity(a, b):
    # from 0 - 1
    return SequenceMatcher(None, a, b).ratio()


def parse_declaration(dec):
    # extract declaration
    left_parenthesis = dec.find("(")
    right_parenthesis = dec.rfind(")")
    
    fuc_type_name = dec[:left_parenthesis].strip()
    fuc_name = fuc_type_name.split()[-1]
    fuc_type = fuc_type_name.replace(fuc_name, '').strip()

    # extract arg
    args_str = dec[left_parenthesis + 1:right_parenthesis].strip()

    # parse "..." in arg
    if "..." in args_str:
        args_str = args_str[:args_str.index("...")]

    # parse arg list
    args_list = [arg.strip() for arg in args_str.split(",")]
    # print(args_list)

    _, args_group = parse_args(args_list)
    return fuc_name, fuc_type, args_group


def calc_score(man_includes, man_declares, llm_includes, llm_declares):
    final_score, score = 0.0, 0.0
    include_weight, declare_weight = 1.0, 5.0
    full_score = len(man_includes) * include_weight + len(man_declares) * declare_weight

    # calculate includes
    if len(llm_includes) <= len(man_includes):
        for inc in llm_includes:
            if inc in man_includes:
                score += 1.0 * include_weight
            else:
                max_similarity = 0
                for man_inc in man_includes:
                    max_similarity = max(max_similarity, calc_str_similarity(inc, man_inc))
                score += max_similarity * include_weight
    else:
        for inc in llm_includes:
            if inc in man_includes:
                score += 1.0 * include_weight
    if syscall in ['stat64', 'sync_file_range2', 'pciconfig_write']:
        print('inc_score=%.3f, inc_full=%.3f, %s'%(score, len(man_includes) * include_weight, syscall))
    
    # calculate declares
    for dec in llm_declares:
        if dec in man_declares:
            score += 1.0 * declare_weight
        else:
            fuc_name, fuc_type, args_group = parse_declaration(dec)
            arg_number = len(args_group)

            # maximum score is 5, calc weight inside
            this_dec_score = 0.0
            this_dec_full_score = 10000.0
            this_dec_final_score = 0.0
            fuc_name_matched = 0
            max_fuc_name_similarity = 0
            sim_fuc_name, sim_fuc_type, sim_args_group = '', '', []
            for man_dec in man_declares:
                man_fuc_name, man_fuc_type, man_args_group = parse_declaration(man_dec)
                man_arg_number = len(man_args_group)
                if calc_str_similarity(man_fuc_name, fuc_name) > max_fuc_name_similarity:
                    max_fuc_name_similarity = calc_str_similarity(man_fuc_name, fuc_name)
                    sim_fuc_name, sim_fuc_type, sim_args_group = man_fuc_name, man_fuc_type, man_args_group
                if fuc_name in man_dec:
                    # same return type +1, same args num +2, same arg name and corresponding type +2
                    this_dec_full_score = 1.0 + 2.0 + (1.0 + 1.0) * man_arg_number
                    this_dec_score += calc_str_similarity(man_fuc_type, fuc_type)
                    if man_arg_number == arg_number:
                        this_dec_score += 2.0
                    # else:
                    #     print('debug for %s'%syscall)
                    l = min(len(args_group), len(man_args_group))
                    tmp_score1, tmp_score2 = 0, 0
                    for i in range(l):
                        # inverse comparison
                        llm_arg_name, llm_arg_type = args_group[-1-i][0], args_group[-1-i][1]
                        man_arg_name, man_arg_type = man_args_group[-1-i][0], man_args_group[-1-i][1]
                        tmp_score1 += calc_str_similarity(llm_arg_name, man_arg_name)
                        tmp_score1 += calc_str_similarity(llm_arg_type, man_arg_type)
                        # sequential comparison
                        llm_arg_name, llm_arg_type = args_group[i][0], args_group[i][1]
                        man_arg_name, man_arg_type = man_args_group[i][0], man_args_group[i][1]
                        tmp_score2 += calc_str_similarity(llm_arg_name, man_arg_name)
                        tmp_score2 += calc_str_similarity(llm_arg_type, man_arg_type)
                    this_dec_score += max(tmp_score1, tmp_score2)
                    
                    this_dec_final_score = (this_dec_score / this_dec_full_score) * declare_weight
                    man_declares.remove(man_dec)
                    fuc_name_matched = 1
                    break
            
            if fuc_name_matched == 0:
                # print('fuc_name=%s, sim_fuc_name=%s, sim=%.3f, %s'%(fuc_name, sim_fuc_name, max_fuc_name_similarity, syscall))
                sim_arg_number = len(sim_args_group)
                this_dec_full_score = 1.0 + 2.0 + (1.0 + 1.0) * sim_arg_number
                this_dec_score += calc_str_similarity(sim_fuc_type, fuc_type)
                if sim_arg_number == arg_number:
                    this_dec_score += 2.0
                # else:
                #     print('debug for %s'%syscall)
                l = min(len(args_group), len(sim_args_group))
                tmp_score1, tmp_score2 = 0, 0
                for i in range(l):
                    # inverse comparison
                    llm_arg_name, llm_arg_type = args_group[-1-i][0], args_group[-1-i][1]
                    man_arg_name, man_arg_type = sim_args_group[-1-i][0], sim_args_group[-1-i][1]
                    tmp_score1 += calc_str_similarity(llm_arg_name, man_arg_name)
                    tmp_score1 += calc_str_similarity(llm_arg_type, man_arg_type)
                    # sequential comparison
                    llm_arg_name, llm_arg_type = args_group[i][0], args_group[i][1]
                    man_arg_name, man_arg_type = sim_args_group[i][0], sim_args_group[i][1]
                    tmp_score2 += calc_str_similarity(llm_arg_name, man_arg_name)
                    tmp_score2 += calc_str_similarity(llm_arg_type, man_arg_type)
                this_dec_score += max(tmp_score1, tmp_score2)
                
                # this_dec_final_score = (this_dec_score / this_dec_full_score) * declare_weight * sqrt(max_fuc_name_similarity)
                this_dec_final_score = (this_dec_score / this_dec_full_score) * declare_weight
                    
            score += this_dec_final_score
    # calc similarity
    final_score = (score / full_score) * 100
    if syscall in ['stat64', 'sync_file_range2', 'pciconfig_write']:
        print('score=%.3f, full=%.3f, final=%.3f, %s'%(score, full_score, final_score, syscall))
    return final_score


if __name__ == '__main__':
    with open('../crawler/syscall_from_manpage.txt', 'r') as f:
        syscalls = [line.strip() for line in f.readlines()]
    
    stat_man = {'VALID': [], 'IOCTL_*': [], 'No wrapper': [], 'Deprecated': [], 'Unimplemented': [], 'OTHERS': [], 'None': []}
    stat_llm = {'VALID': [], 'INCOMPLETE': [], 'None': []}
    acc_threshold = 80
    todo_num, success_num, accurate_num = 0, 0, 0
    syscall_scores = {}
    for syscall in syscalls:
        need_do = 0
        # Load synopsis from man_docs
        fn_man = '../crawler/man_docs/%s.json'%syscall
        # The SYNOPSIS of select_tut is "See select(2)", so refer to it. Only this one exception.
        if syscall == 'select_tut':
            fn_man = '../crawler/man_docs/select.json'
        synop_man = load_synopsis_from_man(fn_man)
        # stat distribution of synopsis from man_docs
        if synop_man == '':
            stat_man['None'].append(syscall)
        elif 'ioctl_' in syscall:
            stat_man['IOCTL_*'].append(syscall)
        elif ('Note' in synop_man and 'wrapper' in synop_man) or 'syscall(SYS_' in synop_man:
            stat_man['No wrapper'].append(syscall)
        elif '[[deprecated]]' in synop_man:
            need_do = 1
            stat_man['Deprecated'].append(syscall)
        elif ('#include' in synop_man and ')' in synop_man):
            need_do = 1
            stat_man['VALID'].append(syscall)
        elif 'Unimplemented system calls' in synop_man:
            stat_man['Unimplemented'].append(syscall)
        else:
            stat_man['OTHERS'].append(syscall)
            
        # Load synopsis from LLM generated
        synop_llm = ''
        fn_llm = './capability/test2/%s.synopsis'%syscall
        if os.path.isfile(fn_llm):
            synop_llm = load_synopsis_from_llm(fn_llm)
            if synop_llm == '':
                stat_llm['None'].append(syscall)
            elif '#include' in synop_llm :
                stat_llm['VALID'].append(syscall)
            elif ');' in synop_llm:
                stat_llm['VALID'].append(syscall)
            else:
                stat_llm['INCOMPLETE'].append(syscall)
        else:
            stat_llm['None'].append(syscall)
        
        if need_do == 1:
            todo_num += 1
            if syscall in stat_llm['VALID']:
                success_num += 1
            man_list = synopsis2list(synop_man)
            llm_list = synopsis2list(synop_llm)

            man_includes, man_declares = filter_lines(syscall, man_list)
            llm_includes, llm_declares = filter_lines(syscall, llm_list)

            this_syscall_score = calc_score(man_includes, man_declares, llm_includes, llm_declares)
            if this_syscall_score >= acc_threshold:
                accurate_num +=1
            elif this_syscall_score < 60:
                print(f'{syscall}: {this_syscall_score:.3f}')
            # print(f'{syscall}: {this_syscall_score:.3f}')

    accurate_rate = accurate_num / todo_num
    success_acc_rate = accurate_num / success_num
    print(f'\n[+] With threshold = {acc_threshold}, LLM capability test accuracy = {accurate_num}/{todo_num} = {100*accurate_rate:.3f}%')
    print(f'\n[+] With threshold = {acc_threshold}, For successfully generated, LLM capability test accuracy = {accurate_num}/{success_num} = {100*success_acc_rate:.3f}%')
    syscall_scores[syscall] = accurate_rate

    print('\nStat for the distribution of synopsis in man_docs:')
    for k in stat_man:
        if k == 'VALID':
            print('[+] %d syscalls\' SYNOPSIS is %s'%(len(stat_man[k]), k))
        else:
            print('[+] %d syscalls\' SYNOPSIS is "%s": '%(len(stat_man[k]), k), stat_man[k])

    print('\nStat for the distribution of synopsis in llm_docs:')
    for k in stat_llm:
        if k == 'VALID':
            print('[+] %d syscalls\' SYNOPSIS is %s'%(len(stat_llm[k]), k))
        else:
            print('[+] %d syscalls\' SYNOPSIS is "%s": '%(len(stat_llm[k]), k), stat_llm[k])
            
    print('\n Stat cross for man and llm:')
    cross_cnt = 0
    for syscall in stat_man['VALID']:
        if syscall in stat_llm['VALID']:
            cross_cnt += 1
        else:
            print('\tnot generated: %s'%syscall)
    print('[+] %d VALID syscalls of man, LLM successfully generates %d VALID.'%(len(stat_man['VALID']), cross_cnt))
                
