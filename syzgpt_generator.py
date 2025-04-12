from generator.program_generator import *
from generator.prompts import *
from generator.program_repair import *
from analyzer.corpus_analyzer import *
import subprocess
import time
import hashlib
import binascii
import shutil
import multiprocessing
from random import shuffle, randint


class GeneratorConfig:
    def __init__(self, model, workdir, max_gen, prompt_type, shot, regen_prob, freq_penalty, local_mode, debug):
        self.model = model
        self.workdir = workdir
        self.max_gen = max_gen
        self.prompt_type = prompt_type
        self.shot = shot
        self.regen_prob = regen_prob
        self.freq_penalty = freq_penalty
        self.local_mode = local_mode
        self.debug = debug
        

class GeneratorResult:
    def __init__(self):
        self.total_token = 0
        self.total_gen_cnt = 0


def parse_corpus(fuzzer_path, corpus_db_path, corpus_dir):
    syz_db_bin = os.path.join(fuzzer_path, 'bin/syz-db')
    parse_cmd = '%s parse %s %s'%(syz_db_bin, corpus_db_path, corpus_dir)
    result = subprocess.run(parse_cmd, shell=True, check=True)
    
    if result.returncode != 0: 
        logger.error('returncode = %d'%result.returncode)
        return False
    logger.success('parse %s at directory %s'%(corpus_db_path, corpus_dir))
    return True


def pack_corpus(fuzzer_path, corpus_dir, corpus_db_path):
    syz_db_bin = os.path.join(fuzzer_path, 'bin/syz-db')
    parse_cmd = '%s pack %s %s'%(syz_db_bin, corpus_dir, corpus_db_path)
    result = subprocess.run(parse_cmd, shell=True, check=True)
    
    if result.returncode != 0: 
        logger.error('returncode = %d'%result.returncode)
        return False
    logger.success('pack %s to %s'%(corpus_dir, corpus_db_path))
    return True


def repair_corpus(fuzzer_path, corpus_dir):
    syz_repair_bin = os.path.join(fuzzer_path, 'bin/syz-repair')
    repair_cmd = '%s %s %s'%(syz_repair_bin, corpus_dir, corpus_dir)
    result = subprocess.run(repair_cmd, shell=True, check=True)
    
    if result.returncode != 0:
        logger.error('returncode = %d'%result.returncode)
        return False
    logger.success('syz-repair %s to %s'%(corpus_dir, corpus_dir))
    return True


def notify_generation_end(workdir):
    end_flag = os.path.join(workdir, 'GENERATION_END')
    try:
        with open(end_flag, 'w') as f:
            pass
        logger.success('notify end by creating %s'%end_flag)
    except:
        logger.error('failed to create %s'%end_flag)


def batch_generate_program(configs, shared_stats, syscalls, call_depend, syz_depend, builtin_syscalls, reverse_index, hash_fn_cnt, covered_calls=[]):
    t0 = time.time()
    shot = configs.shot
    total_tks = 0
    dumb = configs.debug == False
    prog_dir = os.path.join(configs.workdir, 'generated_corpus')
    check_dir(prog_dir)
    
    # load generation_history
    gen_his_path = os.path.join(configs.workdir, 'generation_history.json')
    if os.path.isfile(gen_his_path):
        with open(gen_his_path, 'r') as f:
            generation_history = json.load(f)
    else:
        generation_history = {}
    
    success_cnt = 0
    cnt = 0
    for syscall in syscalls:       
        prev_progs = []        
        if syscall in generation_history:
            # if a program is generated before but the target syscall still not covered in corpus, there are two possible reasons:
            # 1: The generated program are not proper enough, re-generate it with the probability and provide the previous program as prompt.
            # 2: The syscall is not supported because of the environment limitations like hardware or device. So mark as unsupport after 5 attemps.
            if prob(100-configs.regen_prob, 100) or len(generation_history[syscall]) >=3:
                logger.info('syscall %s has already generated %d times. skip with probability %d%%'%(syscall, len(generation_history[syscall]), 100-configs.regen_prob))
                continue
            else:
                for fn in generation_history[syscall]:
                    prev_p = read_prog(os.path.join(configs.workdir, 'generated_corpus', fn))
                    if prev_p != '':
                        prev_progs.append(prev_p)
                logger.debug('load %d failure programs for syscall %s'%(len(generation_history[syscall]), syscall))
                logger.info('re-generate for syscall %s'%syscall)
        try:
            if configs.prompt_type == 1:
                msg_with_hist, query, legacy_query = GEN_WITH_RANDOM(syscall, reverse_index, shot, prev_progs)
            elif configs.prompt_type == 2:
                msg_with_hist, query, legacy_query = GEN_WITH_SYZDEP(syscall, syz_depend, builtin_syscalls, reverse_index, shot, covered_calls, prev_progs)
            elif configs.prompt_type == 3:
                msg_with_hist, query, legacy_query = GEN_WITH_CALLDEP(syscall, call_depend, builtin_syscalls, reverse_index, shot, covered_calls, prev_progs)
            elif configs.prompt_type == 4:
                msg_with_hist, query, legacy_query = GEN_WITH_DEPS_NOSYS(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, shot, covered_calls, prev_progs)
            elif configs.prompt_type == 5:
                msg_with_hist, query, legacy_query = GEN_WITH_FIXED(syscall, shot, prev_progs)
            elif configs.prompt_type == 6:
                msg_with_hist, query, legacy_query = GEN_WITH_DIRECT(syscall)
            else:
                msg_with_hist, query, legacy_query = GEN_WITH_DEPS(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, shot, covered_calls, prev_progs)
            logger.debug('Successfully generate query for %s'%(syscall))
            # response, tks = query_with_history(msg_with_hist, query, configs.model, dumb, 0.5, logger)
            response, tks = query_with_history_new(client, msg_with_hist, query, configs.model, dumb, 0.5, configs.freq_penalty, logger)
            response = replace_unprintables(response)
            if dumb == False:
                print('[Response for %s]\n%s'%(syscall, response))

            # rename the prog and save at prog_dir
            response_bytes = bytes(response, encoding='utf-8')
            h = hashlib.sha1(response_bytes)
            hash_fn = binascii.hexlify(h.digest()).decode('utf-8')
            if hash_fn not in hash_fn_cnt:
                hash_fn_cnt[hash_fn] = 1
                extract_programs(response, syscall, prog_dir, '', hash_fn, configs.local_mode)
                logger.success('Successfully generate syz program %s for %s, cost %d tokens'%(hash_fn, syscall, tks))
                success_cnt += 1
            else:
                logger.warning('Has already generated %d same program %s for %s, cost %d tokens'%(hash_fn_cnt[hash_fn], hash_fn, syscall, tks))
                hash_fn_cnt[hash_fn] += 1
            total_tks += tks
            
            # backup query prompts
            back_query_path = os.path.join(configs.workdir, 'query_prompts', '%s_%d'%(hash_fn, hash_fn_cnt[hash_fn]))
            with open(back_query_path, 'w') as f:
                f.write('%s\n%s'%(legacy_query, response))
            
            # update generation_history
            if syscall not in generation_history:
                generation_history[syscall] = [hash_fn]
            else:
                generation_history[syscall].append(hash_fn)
        except Exception as e:
            logger.exception('[SyzGPT-generator] Exception occured: %s'%e)

        cnt += 1
        if configs.max_gen and cnt >= configs.max_gen:
            logger.warning('reach max generation %d in this batch generation'%configs.max_gen)
            break
        if cnt % 20 == 0 and configs.local_mode == False:
            logger.info('Security 60s sleep every 20 syscalls\' generation for remote mode.')
            sleep(60)
    # save geneartion_history
    with open(gen_his_path, 'w') as f:
        json.dump(generation_history, f, indent=4)
        
    logger.debug('batch generation cost %.2fs and %d tokens for %d/%d syscalls'%(time.time()-t0, total_tks, success_cnt, cnt))
    if cnt > 0: 
        logger.debug('each seed program costs %.2fs and %.2f tokens on average'%((time.time()-t0)/cnt, total_tks/cnt))
    shared_stats['total_token'] += total_tks
    shared_stats['total_gen_cnt'] += cnt
    return total_tks, cnt


def time2sec(t):
    '''
    input: t, str: XdXhXmXs
    return: s, int: YYY 
    '''
    if not t:
        return 0
    if t.isdigit():
        return int(t)
    
    days, hours, minutes, seconds = 0, 0, 0, 0
    if 'd' in t:
        days = int(t.split('d')[0])
        t = t.split('d')[1]
    if 'h' in t:
        hours = int(t.split('h')[0])
        t = t.split('h')[1]
    if 'm' in t:
        minutes = int(t.split('m')[0])
        t = t.split('m')[1]
    if 's' in t:
        seconds = int(t.split('s')[0])
    
    total_seconds = (days * 24 * 3600) + (hours * 3600) + (minutes * 60) + seconds
    return total_seconds


def prob(thres, m):
    '''return True with probability thres/m, or return False'''
    r = randint(1, m)
    return r <= thres


def get_case_insensitive_path(base_path: str, filename: str) -> str:
    # compatible with the uppercase and non-uppercase of the filename (e.g., enabledCalls and EnabledCalls)
    candidates = [
        os.path.join(base_path, filename),
        os.path.join(base_path, filename.capitalize())
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]  # return specified base_path+filename  by default


def get_args():
    parser = argparse.ArgumentParser(description='Program Generator')
    parser.add_argument('-M', '--llm_model', type=str, help='llm model')
    parser.add_argument('-u', '--base_url', type=str, help='api url of llm model')
    parser.add_argument('-k', '--api_key', type=str, help='api key of llm model')
    parser.add_argument("-s", "--fuzzer", type=str, help="path to SyzGPT-fuzzer")
    parser.add_argument('-w', '--workdir', type=str, help='workdir of the fuzzing instance')
    parser.add_argument('-e', '--external_corpus', type=str, help='path to external corpus (like enriched-corpus)')
    parser.add_argument('-f', '--call_file', type=str, help='one-time-gen: syscall list file')
    parser.add_argument('-c', '--calls', type=str, nargs='+', help='one-time-gen: manually specified call lists')
    parser.add_argument('-t', '--prompt_type', type=int, help='general: prompt type, options are 0, 1, 2, 3, 4, 5, 6 (default 0)')
    parser.add_argument('-N', '--N_shot', type=int, help='general: Number of shots for in-context learning (default 3)')
    parser.add_argument('-D', '--delay_period', type=str, help='loop: delay period before generation to let fuzzer go on for a while')
    parser.add_argument('-T', '--generation_period', type=str, help='loop: generation period in time format like 1h10m8s')
    parser.add_argument('-S', '--stop_time', type=str, help='loop: stop after stop_time with format like 24h10m')
    parser.add_argument('-P', '--regen_probability', type=int, help='general: re-generation probability for already generated syscalls, from 0~100 (0 for static, 10 for fuzzing)')
    parser.add_argument('-F', '--freq_penalty', type=float, help='general: frequency_penalty, from 0~1, 0 for openai, 0.2 for local LLMs by default')
    parser.add_argument('-m', '--max_gen', type=int, help='loop: max geneartion in one batch')
    parser.add_argument('-K', '--KGPT', action='store_true', help='add support for KernelGPT')
    parser.add_argument('-d', '--debug', action='store_true', help='debug mode')
    args = parser.parse_args()
    return args


def print_logo():
    print("\n\
  ____             ____ ____ _____                                     _              \n\
 / ___| _   _ ____/ ___|  _ \_   _|     __ _  ___ _ __   ___ _ __ __ _| |_ ___  _ __  \n\
 \___ \| | | |_  / |  _| |_) || |_____ / _` |/ _ \ '_ \ / _ \ '__/ _` | __/ _ \| '__| \n\
  ___) | |_| |/ /| |_| |  __/ | |_____| (_| |  __/ | | |  __/ | | (_| | || (_) | |    \n\
 |____/ \__, /___|\____|_|    |_|      \__, |\___|_| |_|\___|_|  \__,_|\__\___/|_|    \n\
        |___/                          |___/                                          \n\n\
 SyzGPT-generator-v1.0.0")


if __name__ == '__main__':
    print_logo()
    args = get_args()
    model = args.llm_model or LLM_MODEL
    local_mode = False
    freq_penalty = args.freq_penalty or 0
    if args.base_url:
        client.base_url = args.base_url
        client.api_key = args.api_key or 'EMPTY'
        local_mode = True
        # freq_penalty = 0.2
    fuzzer_path = args.fuzzer
    workdir = args.workdir
    max_gen = args.max_gen or None
    prompt_type = args.prompt_type or 0
    shot = args.N_shot or 3
    regen_prob = args.regen_probability or 0
    assert(regen_prob <= 100)
    assert(workdir)
    
    packed_configs = GeneratorConfig(model, workdir, max_gen, prompt_type, shot, regen_prob, freq_penalty, local_mode, args.debug)
    check_model(model)
    
    if workdir[-1] == '/':
        workdir_name = os.path.basename(os.path.dirname(workdir))
        pre_name = os.path.basename(os.path.dirname(os.path.dirname(workdir)))
    else:
        workdir_name = os.path.basename(workdir)
        pre_name = os.path.basename(os.path.dirname(workdir))
    
   
    check_dir(LOG_DIR)
    target_syscalls_dir = os.path.join(workdir, 'target_syscalls')
    query_prompts_dir = os.path.join(workdir, 'query_prompts')
    check_dir(target_syscalls_dir)
    check_dir(query_prompts_dir)
    log_name = time.strftime('syzgpt_generator_%Y-%m-%d', time.localtime())
    log_name += '_%s_%s.log'%(pre_name, workdir_name)
    log_path = os.path.join(LOG_DIR, log_name)
    init_logger(log_file=log_path)
    
    # print some args info
    prompt_type_meaning = {0: 'default', 1: 'random', 2: 'all syz depend', 3: 'all call depend', 4: 'no sys', 5: 'fixed', 6: 'direct'}
    logger.info('SyzGPT is working with strategy: %s, base model: %s, shot: %d, freq_penalty: %.1f'%(prompt_type_meaning[prompt_type], model, shot, freq_penalty))
    if shot == 6:
        logger.warn('There is bug when shot is 6. prompts.py is to be checked.\n')
    # preparse external corpus
    external_done_flag = os.path.join(workdir, '.external_corpus_done')
    external_is_done = os.path.isfile(external_done_flag)
    if args.external_corpus and external_is_done != True:
        external_corpus = args.external_corpus
        logger.info('external corpus flag detected, try to parse %s to workdir %s'%(external_corpus, workdir))
        if os.path.isdir(external_corpus):
            external_corpus_db_path = os.path.join(workdir, 'external_corpus.db')
            parsed_external_corpus_dir = os.path.join(workdir, 'external_corpus')
            pack_corpus(fuzzer_path, external_corpus, external_corpus_db_path)
            parse_corpus(fuzzer_path, external_corpus_db_path, parsed_external_corpus_dir)
        elif os.path.isfile(external_corpus) and external_corpus[-3:] == '.db':
            parsed_external_corpus_dir = os.path.join(workdir, 'external_corpus')
            parse_corpus(fuzzer_path, external_corpus, parsed_external_corpus_dir)
        else:
            logger.error('invalid external_corpus: %s'%external_corpus)
            exit(1)
        with open(external_done_flag, 'w') as f:
            f.write('%d'%(1))
        logger.success('external corpus analysis done, build reverse_index.json')
    elif args.external_corpus and external_is_done == True:
        logger.info('external corpus flag detected and analysis is done')
    
    # load builtin_syscalls and dependency knowledge
    project_dir = os.path.dirname(os.path.realpath(__file__))
    data_dir = os.path.join(project_dir, 'data')
    
    # load syzkaller builtin syscalls
    builtin_syscalls = {}
    with open(os.path.join(data_dir, 'builtin_syscalls.json'), 'r') as f:
        builtin_syscalls = json.load(f)
    
    # load call dependencies
    call_depend = {}
    with open(os.path.join(data_dir, 'call_dependencies/call_dependencies_all.json'), 'r') as f:
        call_depend = json.load(f)
        
    # load syz dependencies
    syz_depend = {}
    syz_depend_path = 'syz_dependencies/syz_depend_inout.json'
    if args.KGPT:
        syz_depend_path = 'KernelGPT_syz_dependencies/syz_depend_inout.json'
    with open(os.path.join(data_dir, syz_depend_path), 'r') as f:
        syz_depend = json.load(f)
    
    # shared dict for results collection
    multi_manager = multiprocessing.Manager()
    shared_stats = multi_manager.dict()
    shared_stats['total_token'] = 0
    shared_stats['total_gen_cnt'] = 0
    
    ################################
    ###   One-time Generation   ###
    ################################
    hash_fn_cnt = {}
    reverse_index = {}
    target_syscalls = args.calls or []
    if args.call_file:
        with open(args.call_file, 'r') as f:
            target_syscalls = [line.strip() for line in f.readlines()]
    if target_syscalls != []:
        logger.info('one-time generation start.')
        if os.path.isfile(os.path.join(workdir, 'reverse_index.json')):
            with open(os.path.join(workdir, 'reverse_index.json'), 'r') as f:
                reverse_index = json.load(f)
        batch_generate_program(packed_configs, shared_stats, target_syscalls, call_depend, syz_depend, builtin_syscalls, reverse_index, hash_fn_cnt, [])
        logger.success('one-time generation done!')
        exit(0)
    
    ################################
    ###         MAIN LOOP        ###
    ################################
    assert(args.generation_period)
    # check if the fuzzer start
    fuzzer_instance_dir = os.path.join(workdir, "instance-0")
    enabled_syscalls_path = get_case_insensitive_path(workdir, "enabledCalls")
    covered_syscalls_path = get_case_insensitive_path(workdir, "coveredCalls")
    while 1:
        if os.path.isdir(fuzzer_instance_dir) and os.path.isfile(enabled_syscalls_path):
            logger.info('fuzzer is running in workdir: %s, EnabledCalls are generated'%workdir)
            break
        logger.warning('fuzzer hasn\'t completely started yet, sleep(60) to wait')
        sleep(60)
    gen_period = time2sec(args.generation_period)
    delay_period = time2sec(args.delay_period)
    if args.base_url and 'api' not in args.base_url:
        one_exec_time = 18
    else:
        one_exec_time = 9
    if max_gen:
        secure_exec_offset = one_exec_time*max_gen
    else:
        secure_exec_offset = time2sec('10m')
    is_first_sleep = 1
    
    enabled_syscalls = []
    covered_syscalls = []
    prev_target_syscalls = []
    reverse_index = {}
    gen_round = 0
    hash_fn_cnt = {}
    
    t_begin = time.time()
    logger.info('Before Main loop: delay sleep(%d) to let fuzzer go on iteself for a while first.'%delay_period)
    sleep(delay_period)
        
    while 1:
        # # break if fuzzer stops (don't multi ctrl+C to exit fuzzer, or the instance-*/ will not be cleared)
        # if not os.path.isdir(fuzzer_instance_dir):
        #     logger.info('Main loop: seems fuzzer has stopped, break loop.')
        #     break
        
        if args.stop_time:
            stop_time = time2sec(args.stop_time)
            dt = int(time.time() - t_begin)
            if dt >= (stop_time - secure_exec_offset - 60):
                logger.info('Main loop: stop after running %d seconds.'%dt)
                break
        check_dir(target_syscalls_dir)
        check_dir(query_prompts_dir)

        if is_first_sleep == 1:
            first_sleep_seconds = max(gen_period-secure_exec_offset, 0)
            logger.info('Main loop: first sleep(%d)'%first_sleep_seconds)
            sleep(first_sleep_seconds)
            is_first_sleep = 0
        else:
            logger.info('Main loop: sleep(%d)'%gen_period)
            sleep(gen_period)
        # load enabled_syscalls and covered_syscalls, calc target_syscalls
        try:
            with open(covered_syscalls_path, 'r') as f:
                covered_syscalls = [line.strip() for line in f.readlines()]
        except:
            # initialize it if the fuzzer side has not totally started
            covered_syscalls = []
        if enabled_syscalls == []:
            with open(enabled_syscalls_path, 'r') as f:
                enabled_syscalls = [line.strip() for line in f.readlines()]
        target_syscalls = list(set(enabled_syscalls) - set(covered_syscalls))
        # record target_syscalls before every generation
        gen_round += 1
        with open(os.path.join(target_syscalls_dir, 'target_syscalls_%dT'%gen_round), 'w') as f:
            for call in target_syscalls:
                f.write('%s\n'%call)
        shuffle(target_syscalls)
        logger.debug('Start to generate for %d target syscalls'%len(target_syscalls), 'with max_gen =', max_gen)

        # parse current fuzzing corpus and get reverse_index
        corpus_db_path = os.path.join(workdir, 'corpus.db')
        corpus_dir = os.path.join(workdir, 'corpus')
        parse_corpus(fuzzer_path, corpus_db_path, corpus_dir)
        with open(os.path.join(workdir, 'reverse_index.json'), 'r') as f:
            reverse_index = json.load(f)

        # create a thread to batch generate programs for target_syscalls
        multiprocessing.Process(target=batch_generate_program, args=(packed_configs, shared_stats, target_syscalls, call_depend, syz_depend, builtin_syscalls, reverse_index, hash_fn_cnt, covered_syscalls)).start()
        logger.info('Multiprocess for batch_generate_program has started with non-block mode. Go for the next loop and wait.')
        prev_target_syscalls = target_syscalls

    logger.info('Main loop end: sleep(%d) to wait util the potential last round generation finished'%(secure_exec_offset))
    sleep(secure_exec_offset)
    logger.debug('Summary: loop generation cost %d tokens for generating %d seed programs'%(shared_stats['total_token'], shared_stats['total_gen_cnt']))
    if shared_stats['total_gen_cnt'] > 0:
        logger.debug('Summary: each seed program costs %.2f tokens on average'%(shared_stats['total_token']/shared_stats['total_gen_cnt']))
    else:
        logger.warning('Summary: No seed programs generated during the loop.')
    notify_generation_end(packed_configs.workdir)
    logger.success('Finish!')