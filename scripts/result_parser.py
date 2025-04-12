'''
Usage samples:

Compared to -c, -C adds Google searching.
1) Check 0days: python result_parser.py -D /path/to/crashes -C -u
2) Check 1days: python result_parser.py -D /path/to/crashes -C
3) Check whether has repro: python result_parser.py -D /path/to/crashes -C -u -r
4) Include keywords in crash title: python result_parser.py -D /path/to/crashes -C -u -k SAN BUG INFO WARN ...
5) Exclude keywords in crash title: python result_parser.py -D /path/to/crashes -C -u -e SYZFATAL SYZFAIL ...

TODOs
'''

import argparse, os, re, glob, pickle, json, requests
from os.path import expanduser
from rich.console import Console
from rich.table import Table
from time import time, localtime, strftime
from fake_useragent import UserAgent
from bs4 import BeautifulSoup, element


ua = UserAgent()
# You need to set http_proxy and https_proxy in environment with export
PROXIES = {'http': os.getenv('http_proxy'), 'https': os.getenv('https_proxy')}
CACHE_DIR = os.path.join(expanduser('~'), '.cache', 'result_parser')


def save_var(fn, var):
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    with open(fn, 'wb') as f:
        pickle.dump(var, f)

def load_var(fn):
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    with open(fn, 'rb') as f:
        return pickle.load(f)
    
def save_cache(fn, cache):
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    with open(fn, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=4)

def load_cache(fn):
    if os.path.isfile(fn):
        with open(fn, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    else:
        cache = {}
    return cache
        
def request_get(url):
    random_header = {'User-Agent': ua.random}
    return requests.get(url=url, headers=random_header, proxies=PROXIES)

def cached_gather_report(cache_ttl=3*86400, flush_cache=False):
    # cache_ttl = 3*86400 # 3 day
    cache_fn = 'reports.pickle'
    cache_path = os.path.join(CACHE_DIR, cache_fn)
    reports = {}
    try:
        if flush_cache == True:
            raise ValueError('Flush cache flag detected')
        cached_reports, cached_time = load_var(cache_path)
        if cache_ttl and ((time()-cached_time) > cache_ttl):
            raise ValueError('Cache expired after TTL: %ds'%cache_ttl)
        print('[+] Load from cache: %s'%cache_path)
        return cached_reports
    except (ValueError, FileNotFoundError) as e:
        print('[x] %s. Request reports from syzbot.'%e)
        reports = gather_report()
        print('[+] Store cache: %s'%cache_path)
        save_var(cache_path, (reports, time()))
        return reports

def gather_report():
    reports = {}
    base_url = 'https://syzkaller.appspot.com'
    # gather reports in open, fixed, and invalid page
    for os in ['upstream', 'linux-6.1', 'linux-5.15']:
        for rep_type in ['open', 'fixed', 'invalid']:
            end_url = '/%s/%s'%(os, rep_type)
            req = request_get(base_url+end_url)
            soup = BeautifulSoup(req.text, "html.parser")
            tables = soup.find_all('table', {'class': 'list_table'})
            for table in tables:
                for case in table.tbody.contents:
                    if type(case) != element.Tag:
                        continue
                    title_td = case.find('td', {"class": "title"})
                    if title_td == None:
                        continue
                    title_str = title_td.find('a').text.strip()
                    bug_href = title_td.find('a').get('href')
                    reports[title_str] = bug_href
    return reports


def get_bug_func(title):
    if ' in ' in title:
        bug_func = title.split(' in ')[1].split(' ')[0].strip()
    else:
        bug_func = ''
    return bug_func


def check_existence(reports, title, syzbot_res, write_cache=True):
    # Set print style in results
    if reports == {}:
        return '[b]--[/]'
    res_str = '[b red]No[/]'

    # Check existence from cache
    if title in syzbot_res:
        if syzbot_res[title] == True:
            res_str = '[b green]Yes[/]'
            return res_str
        elif isinstance(syzbot_res[title], list) == True:
            if len(syzbot_res[title]) == 1:
                print('[Cached][Suspicious][Syzbot] "%s" has the SAME bun func with report [%s]'%(title, syzbot_res[title][0]))
            else:
                print('[Cached][Suspicious][Syzbot] "%s" has the SAME bun func with reports:'%title)
                for e in syzbot_res[title]:
                    print('\t[%s]'%e)
            res_str = '[b yellow]No (S)[/]'
            return res_str
    
    # Check the existence of title and whether it is suspicious by comaring bug_func
    # And update syzbot_res in cache
    bug_func = get_bug_func(title)
    for title_str in reports:
        if title == title_str:
            res_str = '[b green]Yes[/]'
            syzbot_res[title] = True
            break
        report_bug_func = get_bug_func(title_str)
        if bug_func != '' and bug_func == report_bug_func:
            sim_report_hash = '%s: %s'%(title_str, reports[title_str])
            if title not in syzbot_res:
                syzbot_res[title] = [sim_report_hash]
            elif sim_report_hash not in syzbot_res[title] and len(syzbot_res[title]) < 3:
                syzbot_res[title].append(sim_report_hash)
            res_str = '[b yellow]No (S)[/]'  
    if title in syzbot_res and isinstance(syzbot_res[title], list) == True:
        if len(syzbot_res[title]) == 1:
                print('[Suspicious][Syzbot] "%s" has the SAME bun func with report [%s]'%(title, syzbot_res[title][0]))
        else:
            print('[Suspicious][Syzbot] "%s" has the SAME bun func with reports:'%title)
            for e in syzbot_res[title]:
                print('\t[%s]'%e)
    if write_cache == True:
        save_cache(os.path.join(CACHE_DIR, 'syzbot_results.json'), syzbot_res)
    return res_str


# ignore the h3 titles like "XXXXX的图片搜索结果" or "Images for XXXXX"
def check_existence_from_search(title, orig_existence, search_res, write_cache=True):
    # Check the existence from first 10 google search results
    if title in search_res:
        if search_res[title] == True:
            res_str = '[b green]Yes (G)[/]'
            return res_str
        elif isinstance(search_res[title], str) == True:
            res_str = '[b yellow]No (SG)[/]'
            print('[Cached][Suspicious][Google] "%s" has the SAME bug func with search result "%s"'%(title, search_res[title]))
            return res_str

    search_url = 'https://www.google.com/search?q=%s'%title
    req = request_get(search_url)
    soup = BeautifulSoup(req.text, "html.parser")
    main = soup.find_all('div', {'class': 'main'})
    if not main:
        return orig_existence
    h3s = main[0].find_all('h3')
    search_res[title] = False
    res_str = orig_existence
    # h3 contains the title, check them all
    for h3 in h3s:
        h3_title = h3.text.strip()
        if h3_title == '%s的图片搜索结果'%title or h3_title == 'Images for %s'%title:
            continue
        if title in h3_title:
            search_res[title] = True
            res_str = '[b green]Yes (G)[/]'
            break
        bug_func = get_bug_func(title)
        if bug_func and bug_func in h3_title:
            print('[Suspicious][Google] "%s" has the SAME bug func with search result "%s"'%(title, h3_title))
            search_res[title] = h3_title
            res_str = '[b yellow]No (SG)[/]'
            break
    if write_cache == True:
        save_cache(os.path.join(CACHE_DIR, 'search_results.json'), search_res)
    return res_str


def get_workdir(crash_dir):
    wkds = crash_dir.split('/crashes')[0].split('/')
    return '%s/%s'%(wkds[-2], wkds[-1])


def find_workdirs(paths):
    assert(isinstance(paths, list))
    print('[+] Scanning workdirs in %s, which may cost a few seconds...'%paths)
    workdir_list = []
    for path in paths:
        if path[-1] == '/':
            path = path[:-1]
        if os.path.basename(path) == 'crashes':
            workdir_list.append(os.path.dirname(path))
            continue
        find = 0
        for root, dirs, _ in os.walk(path):
            for d in dirs:
                if d == 'crashes':
                    workdir_list.append(root)
                    find = 1
                    break
            if find == 1:
                break
    return workdir_list


def arg_parse():
    parser = argparse.ArgumentParser(description='Analyze crash reports of Syzkaller.')
    # parser.add_argument('crash_dir', help='path to the directory containing crash reports')
    parser.add_argument('-D', '--crash_dirs', type=str, nargs='+', help='path to the directories containing crash reports')
    parser.add_argument('-s', '--search_hash', type=str, nargs='+', help='[Unimpl] search the existence of bug through hash, used with -c, -C')
    parser.add_argument('-S', '--search_title', type=str, nargs='+', help='search the existence of bug through title, used with -c, -C')
    parser.add_argument('-k', '--keyword', nargs='+', help='keyword list that must be included in report title')
    parser.add_argument('-e', '--exclude_keyword', nargs='+', help='keyword list that must be excluded in report title')
    parser.add_argument('-d', '--dumb', action='store_true', help='dumb mode, omit useless output')
    parser.add_argument('-c', '--check_exist', action='store_true', help='check existence of crashes')
    parser.add_argument('-C', '--check_exist_with_search', action='store_true', help='check existence of crashes (add google search)')
    parser.add_argument('-u', '--unique_only', action='store_true', help='unique crash only')
    parser.add_argument('-U', '--unique_only_strict', action='store_true', help='strict unique crash only (ignore suspicious)')
    parser.add_argument('-r', '--has_repro', action='store_true', help='filter out the reports that don\'t have any repro')
    parser.add_argument('-f', '--flush_cache', action='store_true', help='flush cache and re-fetch the reports')

    args = parser.parse_args()
    return args

def main():
    start_t = time()
    args = arg_parse()
    keyword = args.keyword or ['']
    exclude_keyword = ['SYZFATAL', 'SYZFAIL', 'no output from test machine', 'suppressed report']
    if args.exclude_keyword:
        for ek in args.exclude_keyword:
            if ek in exclude_keyword:
                continue
            exclude_keyword.append(ek)
    console = Console()


    total_cnt, has_repro_cnt, print_cnt = 0, 0, 0
    crashes = {}

    # Build crash reports from syzbot
    check_exist = 0
    if args.check_exist:
        check_exist = 1
    if args.check_exist_with_search:
        check_exist = 2
    reports = {}
    syzbot_res_cache, search_res_cache = {}, {}
    if check_exist:
        print('[+] Fetching crash reports from syzbot for existence check')
        reports = cached_gather_report(flush_cache=args.flush_cache)
        console.print('[green][√][%.2fs] Get crash reports done[/]'%(time()-start_t))
        syzbot_res_cache = load_cache(os.path.join(CACHE_DIR, 'syzbot_results.json'))
        search_res_cache = load_cache(os.path.join(CACHE_DIR, 'search_results.json'))

    # search bug
    if args.search_title:
        # Create table for printing results
        table = Table(
            title='[b]Search Results[/]',
            caption='Existence: G for Google searched, S for Suspicious in Syzbot',
            caption_style='b i white',
            show_edge=True,
            show_lines=True,
        )
        table.add_column('Hash', justify='left')
        table.add_column('Title', justify='left')
        table.add_column('Exist', justify='left')
        
        search_results = {}
        for tosearch_title in args.search_title:
            existence = check_existence(reports, tosearch_title, syzbot_res_cache, False)
            if check_exist == 2 and 'No' in existence:
                existence = check_existence_from_search(tosearch_title, existence, search_res_cache, False)
            search_results[tosearch_title] = {'Hash': '-', 'Title': tosearch_title, 'Exist': existence}
            table.add_row('[b]%s[/]'%search_results[tosearch_title]['Hash'], search_results[tosearch_title]['Title'], search_results[tosearch_title]['Exist'])
        console.print(table)
        console.print('[green][√][%.2fs] Done[/]'%(time()-start_t))
        return
        
        
    # Build dict: crashes
    crash_dirs = [os.path.join(workdir, 'crashes') for workdir in find_workdirs(args.crash_dirs)]
    for crash_dir in crash_dirs:
        if not os.path.exists(crash_dir):
            console.print('[red][x] Error: Directory %s does not exist.[/]'%args.crash_dir)
            exit(1)
    for crash_dir in crash_dirs:
        workdir = get_workdir(crash_dir)
        for crash_hash in os.listdir(crash_dir):
            total_cnt += 1
            crash_path = os.path.join(crash_dir, crash_hash)
            if not os.path.isdir(crash_path):
                continue

            # Get title, ignore the ones with exclude keywords
            with open(os.path.join(crash_path, 'description'), 'r') as f:
                title = f.read().strip()
            
            hit_excluding = 0
            for ek in exclude_keyword:
                if ek in title:
                    hit_excluding = 1
                    break
            if hit_excluding:
                continue
            unique_hash = crash_hash + workdir
            crashes[unique_hash] = {'Hash': crash_hash, 'Workdir': workdir}
            crashes[unique_hash]['Title'] = title

            # Check discover time, report0's ctime is the most closed to the discover time.
            min_t = time() + 10000
            max_t = 0
            for fn in os.listdir(crash_path):
                fpath = os.path.join(crash_path, fn)
                stats = os.stat(fpath)
                tmp_min_t = min(stats.st_ctime, stats.st_atime, stats.st_mtime)
                if tmp_min_t < min_t:
                    min_t = tmp_min_t

                if fn == 'description':
                    continue
                tmp_max_t = max(stats.st_ctime, stats.st_atime, stats.st_mtime)
                if tmp_max_t > max_t:
                    max_t = tmp_max_t
            crashes[unique_hash]['Discover'] = min_t
            crashes[unique_hash]['Update'] = max_t

            # Check repros
            syz_repro = len(glob.glob('%s/repro.prog'%crash_path)) + len(glob.glob('%s/repro.txt'%crash_path))
            c_repro = len(glob.glob('%s/repro.cprog'%crash_path)) + len(glob.glob('%s/repro.c'%crash_path))
            crashes[unique_hash]['Syz Repro'], crashes[unique_hash]['C Repro'] = syz_repro, c_repro
            n_repro = syz_repro + c_repro
            if n_repro > 0:
                has_repro_cnt += 1

            # Check existence
            crashes[unique_hash]['Exist'] = check_existence(reports, title, syzbot_res_cache)
            if check_exist == 2 and 'No' in crashes[unique_hash]['Exist']:
                crashes[unique_hash]['Exist'] = check_existence_from_search(title, crashes[unique_hash]['Exist'], search_res_cache)
    
    console.print('[green][√][%.2fs] Traverse crash reports done[/]'%(time()-start_t))
    # Create Table
    table = Table(
        title='[b]Crash Results[/]',
        caption='Existence: G for Google searched, S for Suspicious in Syzbot\n(keyword: %s)\n(exclude keyword: %s)'%(keyword, exclude_keyword),
        caption_style='b i white',
        # expand=True,
        show_edge=True,
        show_lines=True,
        # leading=True
    )

    table.add_column('Hash', justify='left')
    table.add_column('Title', justify='left')
    table.add_column('Syz', justify='left')
    table.add_column('C', justify='left')
    table.add_column('Exist', justify='left')
    table.add_column('Workdir', justify='left')
    table.add_column('Discover(sorted)', justify='left')
    table.add_column('Update', justify='left')

    # Sort the crashes according to discover unix_timestamp
    sorted_crashes = sorted(crashes.keys(), key=lambda x: crashes[x]['Discover'], reverse=True)
    for unique_hash in sorted_crashes:
        d_info = crashes[unique_hash]
        # Filtered by has_repro
        if args.has_repro == True and (d_info['Syz Repro']+d_info['C Repro']) == 0:
            continue
        
        # Filtered by unique_only or strict
        if args.unique_only == True and 'No' not in d_info['Exist']:
            continue
        if args.unique_only_strict == True and '[b red]No[/]' not in d_info['Exist']:
            continue
        
        # Filtered by keyword if any
        match_filter = 0
        for k in keyword:
            if k in d_info['Title']:
                match_filter = 1
                break
        if match_filter == 1 and args.dumb != True:
            discover_time = strftime('%Y-%m-%d %H:%M', localtime(d_info['Discover']))
            update_time = strftime('%Y-%m-%d %H:%M', localtime(d_info['Update']))
            if (d_info['Update']-d_info['Discover']) > 86400:
                update_time = '[cyan]' + update_time + '[/]'
            table.add_row('[b]%s[/]'%d_info['Hash'][:7], d_info['Title'], str(d_info['Syz Repro']), str(d_info['C Repro']), d_info['Exist'], d_info['Workdir'], discover_time, update_time)
            print_cnt += 1

    # print results in rich table style
    console.print(table)

    console.print('\n[b green][+] Cost %.2fs, done! %d/%d valid crashes in total, %d have repro, %d printed.[/]'%(time()-start_t, len(crashes), total_cnt, has_repro_cnt, print_cnt))

if __name__ == '__main__':
    main()