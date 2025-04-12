########################################################
## Deprecated, as we backup rawcover in SyzGPT-fuzzer ##
########################################################

import os, re
import shutil
import requests
import argparse
from fake_useragent import UserAgent
from time import time, sleep

# python backup_rawcover.py ~/experiments/tmp/ -p 52408 -e enriched -t 5s -s 5s
# curl -X GET http://localhost:PORT/rawcover > rawcover


ua = UserAgent()


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


def request_get(url):
    requests.packages.urllib3.disable_warnings()
    random_header = {'User-Agent': ua.random}
    return requests.get(url=url, headers=random_header, verify=False)


def calc_time(time_str):
    time_units = re.findall(r'(\d+)([hms])', time_str)
    total_seconds = 0

    for value, unit in time_units:
        if unit == 'h':
            total_seconds += int(value) * 3600
        elif unit == 'm':
            total_seconds += int(value) * 60
        elif unit == 's':
            total_seconds += int(value)
    return total_seconds


def wake_up(server, port):
    url = '%s:%d'%(server, port)
    r = request_get(url)
    if r.status_code == 200:
        print('[INFO] Wake up server')
    else:
        print('[WARN] Wake up fail')


def get_rawcover(server, port):
    url = '%s:%d/rawcover'%(server, port)
    try:
        print('[INFO] Fetching rawcover from %s, please wait...'%url)
        r = request_get(url)
        rawcover_str = r.text.strip()
        num = len(rawcover_str.split('\n'))
        # print('[DEBUG] rawcover_str=%s'%rawcover_str)
        print('[INFO] Get %d rawcover from %s'%(num, url))
    except:
        print('[ERROR] Fail to get rawcover from %s'%url)
        rawcover_str = ''
    return rawcover_str


def get_args():
    parser = argparse.ArgumentParser(description='Get and store rawcover from syz-manager')
    parser.add_argument('backup_dir', type=str, help='Backup file to this dir')
    parser.add_argument('-m', '--server', type=str, help='Base url of syz-manager http server')
    parser.add_argument('-p', '--port', type=int, nargs='+', help='Port of syz-manager http server')
    parser.add_argument('-e', '--exp_names', type=str, nargs='+', help='Experiment names')
    parser.add_argument('-t', '--backup_cycle', type=str, help='Backup cycle, in s, m, h, d time unit')
    parser.add_argument('-s', '--stop_time', type=str, help='Stop time, in s, m, h, d time unit')
    parser.add_argument('-d', '--delay_time', type=str, help='Delay execution time, in s, m, h, d time unit')
    args = parser.parse_args()
    return args
    

def main():
    start_t = time()
    args = get_args()
    
    if args.delay_time:
        delay_time = calc_time(args.delay_time)
        print('Delay time %s, sleep(%d)'%(args.delay_time, delay_time))
        sleep(delay_time)
    
    check_dir(args.backup_dir)

    if not args.port:
        print('[ERROR] You have to specify port(s) with -p')
        exit(1)

    num_mgr = len(args.port)
    server = args.server or 'http://localhost'
    if args.exp_names:
        outfns = [exp_name+'.rawcover' for exp_name in args.exp_names]
    else:
        outfns = ['%d.rawcover'%p for p in args.port]
    outfiles = [os.path.join(args.backup_dir, fn) for fn in outfns]
    
    stop_flag_path = os.path.join(args.backup_dir, 'STOP_FLAG')
    
    if args.backup_cycle:
        cycle = args.backup_cycle
    else:
        cycle = '1h'
    if args.stop_time:
        stop_time = calc_time(args.stop_time)
    else:
        stop_time = 0
    
    cycle_cnt = 0
    sleep_cnt = 0
    while True:
        sleep_cycle = calc_time(cycle)
        
        # exit while flag is specified
        if os.path.isfile(stop_flag_path):
            os.remove(stop_flag_path)
            break        
        if stop_time and sleep_cnt + 1 >= stop_time:
            break

        # sleep
        cycle_cnt += 1
        print('[cycle cnt %d] sleep(%d)'%(cycle_cnt, sleep_cycle))
        sleep(sleep_cycle)
        sleep_cnt += sleep_cycle

        # backup
        success = 0
        for i, p in enumerate(args.port):
            wake_up(server, p)
            rawcover_str = get_rawcover(server, p)
            if rawcover_str:
                with open(outfiles[i]+'_%s-cycle-of-%s'%(cycle_cnt, cycle), 'wb') as f:
                    f.write(rawcover_str.encode())
                    print('[INFO] Store to %s'%outfiles[i])
                success += 1

        print('[INFO] Successfully get rawcover from %d syz-manager in %.2f seconds'%(success, time()-start_t))

    print('[Bye] Backup rawcover stop!')

if __name__ == '__main__':
    main()