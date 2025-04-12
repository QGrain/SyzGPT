import os, re
import shutil
import argparse
import json
from time import sleep


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False
        

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


def load_config(conf_path):
    with open(conf_path, 'r', encoding='utf-8') as f:
        conf = json.load(f)
    return conf


def store_config(conf_path, conf):
    with open(conf_path, 'w', encoding='utf-8') as f:
        json.dump(conf, f)


def main():
    parser = argparse.ArgumentParser(description='Back up file regularly')
    parser.add_argument('backup_file', type=str, help='File to backup')
    parser.add_argument('backup_dir', type=str, help='Backup file to this dir')
    parser.add_argument('-t', '--backup_cycle', type=str, help='Backup cycle, in s, m, h, d time unit')
    parser.add_argument('-s', '--stop_time', type=str, help='Stop time, in s, m, h, d time unit')
    parser.add_argument('-d', '--delay_time', type=str, help='Delay execution time, in s, m, h, d time unit')
    args = parser.parse_args()
    
    if args.delay_time:
        delay_time = calc_time(args.delay_time)
        print('Delay time %s, sleep(%d)'%(args.delay_time, delay_time))
        sleep(delay_time)

    check_dir(args.backup_dir)

    stop_flag_path = os.path.join(args.backup_dir, 'STOP_FLAG')
    
    if args.backup_cycle:
        cycle = args.backup_cycle
    else:
        cycle = '30m'
    if args.stop_time:
        stop_time = calc_time(args.stop_time)
    else:
        stop_time = 0

    conf = {
        "backup_target": args.backup_file,
        "backup_dir": args.backup_dir,
        "backup_cycle": cycle
    }
    conf_path = os.path.join(args.backup_dir, '.backup_config.json')
    store_config(conf_path, conf)

    cycle_cnt = 0
    sleep_cnt = 0
    while True:
        conf = load_config(conf_path)
        sleep_cycle = calc_time(conf['backup_cycle'])

        # exit while flag is specified
        if os.path.isfile(stop_flag_path):
            os.remove(stop_flag_path)
            break
        
        if stop_time and sleep_cnt + 1 >= stop_time:
            break

        # sleep
        print('sleep(%d)'%sleep_cycle)
        sleep(sleep_cycle)
        sleep_cnt += sleep_cycle
        
        # backup
        cycle_cnt += 1
        backup_to = os.path.join(args.backup_dir, 'corpus.db_%d-cycle-of-%s'%(cycle_cnt, conf['backup_cycle']))
        shutil.copy2(args.backup_file, backup_to)


    print('[Bye] Backup corpus stop!')


if __name__ == '__main__':
    main()

    # todo
    # cli improvements like set up child process for backup