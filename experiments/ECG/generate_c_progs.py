import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from generator.utils import *
# from analyzer.corpus_analyzer import *
import time
import hashlib
import binascii


def filter_C(text):
    lines = text.split('\n')
    pure_c_text = ''
    code_start = 0
    for line in lines:
        if '```' in line:
            code_start ^= 1
            continue
        if code_start == 1:
            pure_c_text += '%s\n'%line
    return pure_c_text


def batch_generate_program(syscalls, workdir, hash_fn_cnt, debug=False, max_gen=None):
    t0 = time.time()
    total_tks = 0
    dumb = debug == False
    prog_dir = os.path.join(workdir, 'generated_c_programs')
    check_dir(prog_dir)
    
    # load generation_history
    gen_his_path = os.path.join(workdir, 'generation_history.json')
    if os.path.isfile(gen_his_path):
        with open(gen_his_path, 'r') as f:
            generation_history = json.load(f)
    else:
        generation_history = {}
    
    success_cnt = 0
    cnt = 0
    for syscall in syscalls:
        msg_with_hist = []
        # msg_with_hist = [{"role": "system", "content": SYS_PROMPT_TEST3}]
               
        try:
            query = f'Now I have a kernel syscall {syscall}, the kernel syscall needs to be invoked from the user mode through the corresponding system call function.\n'
            query += f'Based on the kernel internal function chain. please reason step by step. Don\'t add new kernel module to generate code. Please generate the complete executable C language source code to call the given kernel syscall: {syscall}.\n'
            # query += f'Ensure the C code is gcc-compilable and does not require manual value filling. And only output the complete C code without any other words.'
            response, tks = query_with_history_new(client, msg_with_hist, query, LLM_MODEL, dumb, 0.7, 0, logger)
            response = replace_unprintables(response)
            response = filter_C(response)
            if dumb == False:
                print('[Response for %s]\n%s'%(syscall, response))

            # rename the prog and save at prog_dir
            response_bytes = bytes(response, encoding='utf-8')
            h = hashlib.sha1(response_bytes)
            hash_fn = binascii.hexlify(h.digest()).decode('utf-8')
            if hash_fn not in hash_fn_cnt:
                hash_fn_cnt[hash_fn] = 1
                extract_programs(response, syscall, prog_dir, '', hash_fn)
                logger.success('Successfully generate program %s for %s, cost %d tokens'%(hash_fn, syscall, tks))
                success_cnt += 1
            else:
                logger.warning('Has already generated %d same program %s for %s, cost %d tokens'%(hash_fn_cnt[hash_fn], hash_fn, syscall, tks))
                hash_fn_cnt[hash_fn] += 1
            total_tks += tks
            
            # backup query prompts
            back_query_path = os.path.join(workdir, 'query_prompts', '%s_%d'%(hash_fn, hash_fn_cnt[hash_fn]))
            with open(back_query_path, 'w') as f:
                f.write('%s\n%s'%(query, response))
            
            # update generation_history
            if syscall not in generation_history:
                generation_history[syscall] = [hash_fn]
            else:
                generation_history[syscall].append(hash_fn)
        except Exception as e:
            logger.exception('[SyzGPT-generator] Exception occured: %s'%e)

        cnt += 1
        if max_gen and cnt >= max_gen:
            logger.warning('reach max generation %d in this batch generation'%max_gen)
            break
        if cnt % 20 == 0:
            logger.info('Security 60s sleep every 20 syscalls\' generation.')
            sleep(60)
    # save geneartion_history
    with open(gen_his_path, 'w') as f:
        json.dump(generation_history, f, indent=4)
        
    logger.debug('batch generation cost %.2fs and %d tokens for %d/%d syscalls'%(time.time()-t0, total_tks, success_cnt, cnt))
    return total_tks


def get_args():
    parser = argparse.ArgumentParser(description='Migrated from ECG: C Program Generator')
    parser.add_argument('-M', '--llm_model', type=str, help='local llm model')
    parser.add_argument('-u', '--base_url', type=str, help='url to local llm model')
    parser.add_argument('-k', '--api_key', type=str, help='api key for base url llm model')
    parser.add_argument('-s', '--syzkaller', type=str, help='path to syzkaller fuzzer')
    parser.add_argument('-w', '--workdir', type=str, help='workdir of the fuzzing instance')
    parser.add_argument('-f', '--call_file', type=str, help='one-time-gen: syscall list file')
    parser.add_argument('-c', '--calls', type=str, nargs='+', help='one-time-gen: manually specified call lists')
    parser.add_argument('-m', '--max_gen', type=int, help='loop: max geneartion in one batch')
    parser.add_argument('-d', '--debug', action='store_true', help='debug mode')
    args = parser.parse_args()
    return args
    

if __name__ == '__main__':
    args = get_args()
    # model = args.llm_model or LLM_MODEL
    if args.base_url:
        client.base_url = args.base_url
        assert(args.api_key)
        client.api_key = args.api_key
    syzkaller_path = args.syzkaller
    workdir = args.workdir
    max_gen = args.max_gen or None
    assert(workdir)
    
    if workdir[-1] == '/':
        workdir_name = os.path.basename(os.path.dirname(workdir))
        pre_name = os.path.basename(os.path.dirname(os.path.dirname(workdir)))
    else:
        workdir_name = os.path.basename(workdir)
        pre_name = os.path.basename(os.path.dirname(workdir))
    
    
    check_dir(LOG_DIR)
    query_prompts_dir = os.path.join(workdir, 'query_prompts')
    check_dir(query_prompts_dir)
    log_name = time.strftime('generate_c_%Y-%m-%d', time.localtime())
    log_name += '_%s_%s.log'%(pre_name, workdir_name)
    log_path = os.path.join(LOG_DIR, log_name)
    init_logger(log_file=log_path)

    
    ################################
    ###   One-time Generration   ###
    ################################
    hash_fn_cnt = {}
    target_syscalls = args.calls or []
    if args.call_file:
        with open(args.call_file, 'r') as f:
            target_syscalls = [line.strip() for line in f.readlines()]
    if target_syscalls != []:
        logger.info('one-time generation start.')
        batch_generate_program(target_syscalls, workdir, hash_fn_cnt, args.debug, max_gen)
        logger.success('one-time generation done!')
        exit(0)