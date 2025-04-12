import argparse, os, json
import matplotlib.pyplot as plt


# Default plot style
DEF_LINE_STY = {
    'marker': '.',
    'markersize': 12.0,
    'linewidth': 3.5
}

# Global style configuration
PLT_STY = {
    'SyzGPT': {'color': '#2ca02c', 'marker': 'o', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']},      # 绿色，圆形
    'Syzkaller': {'color': '#1f77b4', 'marker': 'v', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']},   # 蓝色，倒三角形
    'MoonShine': {'color': '#ff7f0e', 'marker': 'D', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']},   # 黄色，菱形
    'Healer': {'color': '#d62728', 'marker': 's', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']},      # 红色，正方形
    'ACTOR': {'color': '#9467bd', 'marker': '^', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']},       # 紫色，正三角形
    'MOCK': {'color': '#8c564b', 'marker': 'p', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']},        # 棕色，五角星
    'ECG': {'color': '#e377c2', 'marker': 'h', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']},         # 粉色，六边形
    'KernelGPT': {'color': '#7f7f7f', 'marker': '*', 'markersize': DEF_LINE_STY['markersize'], 'linewidth': DEF_LINE_STY['linewidth']}    # 深灰色，星形
}


def validate_fn(fn):
    assert isinstance(fn, str)
    fn = fn.replace(' ', '_')
    fn = fn.replace('/', '-')
    return fn

def sec2time(s):
    '''
    input: s, int: YYY
    return: t, str: XdXhXmXs
    '''
    if isinstance(s, str):
        try:
            time2sec(s)
        except:
            print('[x] Error: invalid time format %s'%s)
            exit(1)
        return s
    days, seconds = divmod(s, 24 * 3600)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    time_str = ''
    if days > 0:
        time_str += f'{days}d'
    if hours > 0:
        time_str += f'{hours}h'
    if minutes > 0:
        time_str += f'{minutes}m'
    if seconds > 0 or not time_str:
        time_str += f'{seconds}s'

    return time_str

def time2sec(t):
    '''
    input: t, str: XdXhXmXs
    return: s, int: YYY 
    '''
    if isinstance(t, int):
        try:
            sec2time(t)
        except:
            print('[x] Error: invalid time second number %d'%t)
            exit(1)
        return t
    if t.isdigit():
        return int(t)
    
    units = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
    seconds = 0
    
    num = ''
    for c in t:
        if c.isdigit():
            num += c
        elif c in units:
            seconds += int(num) * units[c]
            num = ''
            
    return seconds

def read_log(log_path):
    '''
    input: log_path, str: path to the log file
    return: log_list, list: list of log chunks (type: dict[str]=int)
    '''
    log_list = []
    with open(log_path, 'r', encoding='utf-8') as f:
        log_chunk = ''
        for line in f:
            log_chunk += line.strip()
            if log_chunk.endswith('}'):
                try:
                    log_dict = json.loads(log_chunk)
                    for k in log_dict:
                        log_dict[k] = int(log_dict[k])
                    log_list.append(log_dict)
                    log_chunk = ''
                except json.JSONDecodeError as e:
                    print('[x] Errot parsing log_chunk to JSON: %s'%log_chunk)
                    log_chunk = ''
    return log_list

def search_log_by_time(log_list, t):
    seconds = time2sec(t)
    d = (log_list[-1]['uptime']-log_list[0]['uptime']) / len(log_list)
    n = int(seconds / d)
    n = max(0, n)
    n = min(len(log_list)-1, n)
    i = n
    if log_list[i]['uptime'] < seconds:
        while i < len(log_list)-1:
            i += 1
            if abs(log_list[i]['uptime']-seconds) > abs(log_list[i-1]['uptime']-seconds):
                return i, log_list[i-1]
    else:
        while i > 0:
            i -= 1
            if abs(log_list[i]['uptime']-seconds) > abs(log_list[i+1]['uptime']-seconds):
                return i, log_list[i+1]
    return i, log_list[i]

def search_log_by_cover(log_list, cover):
    for i, chunk in enumerate(log_list):
        if chunk['coverage'] >= cover:
            return i, chunk
    return None, None

def sample_log_by_key(log_list, key, end_val, interval_val, range_thres, delta_thres):
    sample_chunks = []
    last_val = 0
    sample_chunks.append(log_list[0])
    for chunk in log_list:
        delta_val = chunk[key] - last_val
        last_val = chunk[key]
        if chunk[key] == 0:
            continue
        if chunk[key] >= range_thres:
            break
        if delta_val > delta_thres and chunk not in sample_chunks:
            sample_chunks.append(chunk)
    
    for val in range(range_thres, end_val+1, interval_val):
        if key == 'coverage':
            match_chunk = search_log_by_cover(log_list, val)[1]
        elif key == 'uptime':
            match_chunk = search_log_by_time(log_list, sec2time(val))[1]
        else:
            print('[x] Error: invalid key %s'%key)
            exit(1)
        if match_chunk not in sample_chunks:
            sample_chunks.append(match_chunk)
    if key == 'coverage':
        match_end_chunk = search_log_by_cover(log_list, end_val)[1]
        if match_end_chunk not in sample_chunks:
            sample_chunks.append(match_end_chunk)
    return sample_chunks

def sample_log_evenly(log_list, end_t, interval_t):
    return sample_log_by_key(log_list, 'uptime', time2sec(end_t), time2sec(interval_t), 0, 0)

def sample_log_by_cover(log_list, end_cover, interval_cover):
    # cover range_thres is set to 50000 as the data is sparse
    return sample_log_by_key(log_list, 'coverage', end_cover, interval_cover, 50000, 10)

def sample_log_by_time(log_list, end_t, interval_t):
    # time range_thres is set to 3600 as the data is sparse
    return sample_log_by_key(log_list, 'uptime', time2sec(end_t), time2sec(interval_t), 3600, 10)

def print_log(log_chunk, key=None):
    uptime_sec = log_chunk['uptime']
    uptime_time = sec2time(uptime_sec)
    print('[+] print log_chunk')
    print('    uptime: %d, %s'%(uptime_sec, uptime_time))
    if key != None and key != []:
        for k in key:
            if k in log_chunk:
                print('    %s: %s'%(k, log_chunk[k]))
    else:
        # by default
        default = ['coverage', 'corpus', 'crashes', 'crash types', 'exec total']
        for k in default:
            print('    %s: %s'%(k, log_chunk[k]))
            
def calc_ratio(log_chunk, key=['new inputs' ,'exec total']):
    uptime_sec = log_chunk['uptime']
    uptime_time = sec2time(uptime_sec)
    # print(f'[+] calc ratio of {key[0]}/{key[1]}')
    # print('    uptime: %d, %s'%(uptime_sec, uptime_time))
    try:
        if log_chunk[key[1]] == 0:
            return 0
        ratio = float(log_chunk[key[0]]) / float(log_chunk[key[1]]) * 100
    except:
        ratio = 0
    # print(f'    ratio: {ratio:.2f}%')
    return ratio

def stat_log(log_list):
    num_chunk = len(log_list)
    print('[-] This bench file contains %d log chunk'%num_chunk)
    print_log(log_list[-1])
    
def _save_plot(out_dir, fn):
    plt.tight_layout()
    png_path = os.path.join(out_dir, validate_fn('%s.png'%(fn)))
    eps_path = os.path.join(out_dir, validate_fn('%s.eps'%(fn)))
    plt.savefig(png_path, dpi=600, format='png', bbox_inches='tight', pad_inches=0)
    plt.savefig(eps_path, dpi=600, format='eps', bbox_inches='tight', pad_inches=0)
    plt.close()

def plot(title, d, key, legend, time, n_ticks, out_dir):
    plt.figure(figsize=(16, 10))
    plt.title(title, fontsize=28, fontweight='bold')
    plt.xlabel('Time (hour)', fontsize=28, fontweight='bold')
    if key == 'BBhitCnt':
        plt.ylabel('FuncHitCnt', fontsize=28, fontweight='bold')
    elif '-exec' in key:
        plt.ylabel('VIR (%)', fontsize=28, fontweight='bold')
    else:
        plt.ylabel(key, fontsize=28, fontweight='bold')

    for legend_name in legend:
        x_data = [i for i in range(len(d[legend_name]))]
        y_data = [d[legend_name][j][key] for j in range(len(d[legend_name]))]
        
        # use default style or custom style
        if legend_name in PLT_STY:
            style = PLT_STY[legend_name]
            plt.plot(x_data, y_data, label=legend_name, **style)
        else:
            plt.plot(x_data, y_data, label=legend_name, marker='.', markersize=14.0, linewidth=3.5)

    plt.xlim(left=0, right=len(x_data)-1)
    plt.ylim(bottom=0)
    plt.legend(fontsize=28)
    plt.grid()
    
    x_ticks = [int(len(x_data)/n_ticks)*i for i in range(n_ticks+1)]
    x_label = [str(int(len(x_data)/n_ticks)*i) for i in range(n_ticks+1)]
    plt.xticks(x_ticks, x_label, fontsize=28, fontweight='bold')
    plt.yticks(fontsize=28, fontweight='bold')
    _save_plot(out_dir, '%s-%s-interval-60s'%(key, time))
    print('[+] plot() done for %s-%s'%(key, time))

def plot_ratio_by_cover(title, d, ratio_name, legend, out_dir):
    plt.figure(figsize=(16, 10))
    
    for legend_name in legend:
        x_data = [chunk['coverage'] for chunk in d[legend_name]]
        y_data = [chunk[ratio_name] for chunk in d[legend_name]]
        
        # use default style or custom style
        if legend_name in PLT_STY:
            style = PLT_STY[legend_name]
            plt.plot(x_data, y_data, label=legend_name, **style)
        else:
            plt.plot(x_data, y_data, label=legend_name, marker='.', markersize=14.0, linewidth=3.5)
    
    plt.xlabel('Coverage', fontsize=24, fontweight='bold')
    plt.ylabel(f'VIR (%)', fontsize=24, fontweight='bold')
    plt.title(title, fontsize=24, fontweight='bold')
    plt.grid(True)
    plt.legend(fontsize=28)
    
    plt.xlim(left=0, right=200000)
    plt.ylim(bottom=0)
    
    plt.xticks(fontsize=22, fontweight='bold')
    plt.yticks(fontsize=22, fontweight='bold')
    
    _save_plot(out_dir, '%s_ratio_by_coverage'%(title))
    print('[+] plot() done for %s'%(title))

def plot_ratio_over_key(title, d, ratio_name, key, legend, out_dir):
    plt.figure(figsize=(16, 10))
    
    max_x = 0
    for legend_name in legend:
        x_data = [chunk[key] for chunk in d[legend_name]]
        y_data = [chunk[ratio_name] for chunk in d[legend_name]]
        max_x = max(max(x_data), max_x)
        # use default style or custom style
        if legend_name in PLT_STY:
            style = PLT_STY[legend_name]
            plt.plot(x_data, y_data, label=legend_name, **style)
        else:
            plt.plot(x_data, y_data, label=legend_name, marker='.', markersize=14.0, linewidth=3.5)
    
    plt.xlabel(key, fontsize=24, fontweight='bold')
    plt.ylabel(f'VIR (%)', fontsize=24, fontweight='bold')
    plt.title(title, fontsize=24, fontweight='bold')
    plt.grid(True)
    plt.legend(fontsize=28)
    
    if key == 'coverage':
        right_lim = (max_x//25000+1)*25000
        plt.xlim(left=0, right=right_lim)
    elif key == 'uptime':
        plt.xlim(left=0, right=86400)
        plt.xticks([i*3600 for i in range(0, 25, 4)], [f'{i}h' for i in range(0, 25, 4)])
    plt.ylim(bottom=0)
    
    plt.xticks(fontsize=22, fontweight='bold')
    plt.yticks(fontsize=22, fontweight='bold')
    
    _save_plot(out_dir, '%s_ratio_over_%s'%(title, key))
    print('[+] plot() done for %s'%(title))

def calc_avg(group_data):
    '''
    input: group_data, (type: list[list[log_chunk]]), log_chunk is dict[str]=list[int]
    return: avg_data, upper_data, lower_data (type: list[log_chunk])
    '''
    if len(group_data) == 0:
        return [], [], []
    elif len(group_data) == 1:
        return group_data[0], group_data[0], group_data[0]
    avg_data, upper_data, lower_data = [], [], []
    group_size = len(group_data)
    # chunk_num = len(group_data[0])
    chunk_num = max([len(group_data[i]) for i in range(group_size)])
    # fill the last chunk to the same length in group_data
    for i in range(group_size):
        if len(group_data[i]) < chunk_num:
            last_chunk = group_data[i][-1]
            for j in range(len(group_data[i]), chunk_num):
                group_data[i].append(last_chunk)
    chunk_keys = list(group_data[0][0].keys())
    for i in range(chunk_num):
        avg_chunk, upper_chunk, lower_chunk = {}, {}, {}
        for k in chunk_keys:
            avg_chunk[k] = 0
            upper_chunk[k] = 0
            lower_chunk[k] = 0
        for j in range(group_size):
            for k in chunk_keys:
                try:
                    val = group_data[j][i][k]
                except:
                    val = 0
                avg_chunk[k] += val / group_size
                upper_chunk[k] = max(upper_chunk[k], val)
                lower_chunk[k] = min(lower_chunk[k], val)
        avg_data.append(avg_chunk)
        upper_data.append(upper_chunk)
        lower_data.append(lower_chunk)
    return avg_data, upper_data, lower_data

def calc_avg_over_key(group_data, ratio_name, key, min_interval):
    if len(group_data) == 0:
        return [], [], []
    elif len(group_data) == 1:
        return group_data[0], group_data[0], group_data[0]
    
    # Collect all key values to build the full set of x-axis
    key_set = set()
    for data in group_data:
        for chunk in data:
            key_set.add(chunk[key])
    key_list = sorted(list(key_set))
    
    # Filter key_val < min_interval, remove points with small intervals
    filtered_key = [key_list[0]]  # Keep the first point
    for key_val in key_list[1:]:
        if key == 'uptime' and key_val < 3600 and key_val - filtered_key[-1] >= min_interval/60:
            filtered_key.append(key_val)
            continue
        if key == 'coverage' and key_val < 21000 and key_val - filtered_key[-1] >= min_interval/100:
            filtered_key.append(key_val)
            continue
        if key_val - filtered_key[-1] >= min_interval:
            filtered_key.append(key_val)
    key_list = filtered_key
    
    # Linear interpolation
    interpolated_data = []
    for data in group_data:
        # Build the mapping from key to ratio_name
        key_to_ratio = {chunk[key]: chunk[ratio_name] for chunk in data}
        interpolated = []
        for key_val in key_list:
            if key_val in key_to_ratio:
                chunk = next(c for c in data if c[key] == key_val)
                interpolated.append(chunk)
            else:
                # Find the nearest left and right known points for interpolation
                left_key_val = max([c for c in key_to_ratio.keys() if c < key_val], default=None)
                right_key_val = min([c for c in key_to_ratio.keys() if c > key_val], default=None)
                
                if left_key_val is None or right_key_val is None:
                    continue
                    
                left_ratio = key_to_ratio[left_key_val]
                right_ratio = key_to_ratio[right_key_val]
                
                # Linear interpolation to calculate ratio
                ratio = left_ratio + (right_ratio - left_ratio) * (key_val - left_key_val) / (right_key_val - left_key_val)
                
                # Construct the interpolated point
                chunk = next(c for c in data if c[key] == left_key_val).copy()
                chunk[key] = key_val
                chunk[ratio_name] = ratio
                interpolated.append(chunk)
                
        interpolated_data.append(interpolated)
    
    # Calculate average
    avg_data, upper_data, lower_data = [], [], []
    
    for i in range(len(key_list)):
        chunks_at_key = [data[i] for data in interpolated_data if i < len(data)]
        if not chunks_at_key:
            continue
            
        avg_chunk = chunks_at_key[0].copy()
        upper_chunk = chunks_at_key[0].copy()
        lower_chunk = chunks_at_key[0].copy()
        
        for k in avg_chunk.keys():
            values = []
            for c in chunks_at_key:
                try:
                    values.append(c[k])
                except:
                    values.append(0)
            avg_chunk[k] = sum(values) / len(values)
            upper_chunk[k] = max(values)
            lower_chunk[k] = min(values)
            
        avg_data.append(avg_chunk)
        upper_data.append(upper_chunk)
        lower_data.append(lower_chunk)
        
    return avg_data, upper_data, lower_data


def get_args():
    parser = argparse.ArgumentParser(description='Parse fuzzing results from bench files')
    parser.add_argument('-b', '--bench_file', type=str, nargs='*', help='bench file(s) to parse')
    parser.add_argument('-t', '--time', type=str, help='print the results around specified time')
    parser.add_argument('-T', '--title', type=str, default='6.6', help='title of the plot, use with -p')
    parser.add_argument('-i', '--interval', type=str, default='1h', help='sample interval (e.g. 10m, 30m, 1h), 1h by default')
    parser.add_argument('-k', '--keys', type=str, nargs='*', help='keys to parse')
    parser.add_argument('-r', '--ratio', type=str, nargs='*', help='calc ratio of 2 keys')
    parser.add_argument('-l', '--legend', type=str, nargs='*', help='legends for multi bench files, work with -p')
    parser.add_argument('-a', '--average', type=int, default=1, help='average number, work with -p')
    parser.add_argument('-p', '--plot', action='store_true', help='plot, work with -b, -t, -k, -l')
    parser.add_argument('-s', '--stat', action='store_true', help='stat the bench log, this option is prior to the others')
    parser.add_argument('-o', '--out_dir', type=str, default='.', help='out dir to save the plot fig')
    args = parser.parse_args()
    return args

def main():
    args = get_args()
    keys = args.keys or []
    ratio_keys = args.ratio or []
    legend = args.legend or []
    os.makedirs(args.out_dir, exist_ok=True)
    
    if args.bench_file:
        bench_list = args.bench_file
        bench_num = len(bench_list)
        assert bench_num % args.average == 0, 'The number of benches must be divisible by the average number'
    else:
        print('[x] You have to specify at least one bench file through -b/--bench_file')
        exit(1)
        
    if ratio_keys != [] and len(ratio_keys) != 2:
        print('[x] You have to specify exactly 2 keys through -r/--ratio')
        exit(1)
    else:
        avg_ratio = 0.0
        ratio_name = f'{ratio_keys[0]}-{ratio_keys[1]}'
        ratioXcov_name = f'{ratio_keys[0]}-{ratio_keys[1]}Xcov'
        keys.append(ratio_name)
        keys.append(ratioXcov_name)
    
    if args.plot:
        assert keys != [], 'You have to specify at least one key through -k/--keys'
        assert len(keys) == len(set(keys)), 'The keys must be unique'
        assert legend != [] and len(legend) == len(set(legend)), 'The legends must be specified and unique'
    
    if args.time:
        t = args.time
    else:
        print('[x] You\'d better specify a time through -t, use default: 12h')
        t = '12h'

    if time2sec(t) % time2sec(args.interval) != 0:
        print('[x] Warning: the end time should be divisible by the interval time')

    plot_data, plot_ratio_data_cover, plot_ratio_data_time, plot_ratioXcov_data_time = {}, {}, {}, {}
    group_data, group_ratio_data_cover, group_ratio_data_time, group_ratioXcov_data_time = [], [], [], []
    for i, log_path in enumerate(bench_list):
        print('[+] Proccessing %s'%log_path)
        log_list = read_log(log_path)
        
        max_ratio = 0
        for chunk in log_list:
            ratio = calc_ratio(chunk, ratio_keys)
            max_ratio = max(max_ratio, ratio)
        print(f'[+] Max ratio of {ratio_name} of {log_path}: {max_ratio:.2f}%')
        
        if args.stat == True:
            stat_log(log_list)
            continue
       
        end_idx, end_chunk = search_log_by_time(log_list, t)
        
        if ratio_keys != []:
            ratio = calc_ratio(end_chunk, ratio_keys)
            end_chunk[ratio_name] = ratio
            end_chunk[ratioXcov_name] = ratio * end_chunk['coverage']
            avg_ratio += ratio / bench_num
        
        if args.plot == False:
            print_log(end_chunk, keys)
            continue
        sample_chunks = sample_log_evenly(log_list, t, args.interval)
        for chunk in sample_chunks:
            ratio = calc_ratio(chunk, ratio_keys)
            chunk[ratio_name] = ratio
        group_data.append(sample_chunks)
        if (i+1) % args.average == 0:
            avg_data, upper_data, lower_data = calc_avg(group_data)
            group_data = []
            plot_data[legend[int(i/args.average)]] = avg_data
        
        sample_chunks_cover = sample_log_by_cover(log_list, end_chunk['coverage'], 7500)
        for chunk in sample_chunks_cover:
            ratio = calc_ratio(chunk, ratio_keys)
            chunk[ratio_name] = ratio
        group_ratio_data_cover.append(sample_chunks_cover)
        if (i+1) % args.average == 0:
            avg_data, upper_data, lower_data = calc_avg_over_key(group_ratio_data_cover, ratio_name, 'coverage', 3000)
            group_ratio_data_cover = []
            plot_ratio_data_cover[legend[int(i/args.average)]] = avg_data
    
        sample_chunks_time = sample_log_by_time(log_list, end_chunk['uptime'], 600)
        for chunk in sample_chunks_time:
            ratio = calc_ratio(chunk, ratio_keys)
            chunk[ratio_name] = ratio
            chunk[ratioXcov_name] = ratio * chunk['coverage']
        group_ratio_data_time.append(sample_chunks_time)
        group_ratioXcov_data_time.append(sample_chunks_time)
        if (i+1) % args.average == 0:
            avg_data, upper_data, lower_data = calc_avg_over_key(group_ratio_data_time, ratio_name, 'uptime', 3600)
            group_ratio_data_time = []
            plot_ratio_data_time[legend[int(i/args.average)]] = avg_data
            avg_data, upper_data, lower_data = calc_avg_over_key(group_ratioXcov_data_time, ratioXcov_name, 'uptime', 3600)
            group_ratioXcov_data_time = []
            plot_ratioXcov_data_time[legend[int(i/args.average)]] = avg_data
    

    if ratio_keys != []:
        print(f'[+] Average {ratio_name} of {bench_num} benches: {avg_ratio:.2f}%')
    
    if args.plot == True:
        n_ticks = 6
        for k in keys:
            if k == ratio_name or k == ratioXcov_name:
                continue
            plot(args.title, plot_data, k, legend, t, n_ticks, args.out_dir)
        if ratio_keys != []:
            plot_ratio_over_key(args.title, plot_ratio_data_cover, ratio_name, 'coverage', legend, args.out_dir)
            plot_ratio_over_key(args.title, plot_ratio_data_time, ratio_name, 'uptime', legend, args.out_dir)
            plot_ratio_over_key(args.title, plot_ratioXcov_data_time, ratioXcov_name, 'uptime', legend, args.out_dir)
    print('[+] bench_parser done!')
            

if __name__ == '__main__':
    main()
    # Plot metrics over time:
    # python3 bench_parser.py -b ../test/cmp1.log ../test/cmp2.log ... -t 1d12h -k coverage corpus -l cmp1 cmp2 lab1 lab2 -p -o /path/to/save/
    
    # Calc VIR at a specific time:
    # python3 bench_parser.py -b ../test/cmp1.log ../test/cmp2.log ... -t 1d12h -r 'new inputs' 'exec total'
    
    # VIR Plot:
    # 6.6
    # python3 bench_parser.py -b .\example-logs\v6-1-SyzGPT-loop.log .\example-logs\v6-2-SyzGPT-loop.log .\example-logs\v6-3-SyzGPT-loop.log .\example-logs\v6-1-syzkaller.log .\example-logs\v6-2-syzkaller.log .\example-logs\v6-3-syzkaller.log .\example-logs\v6-1-moonshine.log .\example-logs\v6-2-moonshine.log .\example-logs\v6-2-moonshine.log .\example-logs\v6-1-ecg.log .\example-logs\v6-2-ecg.log .\example-logs\v6-3-ecg.log .\example-logs\v6-1-actor.log .\example-logs\v6-3-actor.log .\example-logs\v6-4-actor.log  -t 24h -i 1h -l SyzGPT Syzkaller MoonShine ECG ACTOR -a 3 -T 6.6 -r 'new inputs' 'exec total' -p
    # 5.15
    # python3 .\bench_parser.py -b ..\benchdir\v5-1-SyzGPT-loop.log ..\benchdir\v5-2-SyzGPT-loop.log ..\benchdir\v5-3-SyzGPT-loop.log ..\benchdir\v5-1-syzkaller.log ..\benchdir\v5-2-syzkaller.log ..\benchdir\v5-3-syzkaller.log ..\benchdir\v5-4-moonshine.log ..\benchdir\v5-5-moonshine.log ..\benchdir\v5-6-moonshine.log ..\benchdir\v5-1-ecg.log ..\benchdir\v5-2-ecg.log ..\benchdir\v5-3-ecg.log ..\benchdir\v5-1-actor.log ..\benchdir\v5-2-actor.log ..\benchdir\v5-3-actor.log  -t 24h -i 1h -l SyzGPT Syzkaller MoonShine ECG ACTOR -a 3 -T 5.15 -r 'new inputs' 'exec total' -p
    # 4.19
    # python3 .\bench_parser.py -b ..\benchdir\v4-1-SyzGPT-loop.log ..\benchdir\v4-2-SyzGPT-loop.log ..\benchdir\v4-3-SyzGPT-loop.log ..\benchdir\v4-1-syzkaller.log ..\benchdir\v4-2-syzkaller.log ..\benchdir\v4-3-syzkaller.log ..\benchdir\v4-1-moonshine.log ..\benchdir\v4-2-moonshine.log ..\benchdir\v4-3-moonshine.log ..\benchdir\v4-1-ecg.log ..\benchdir\v4-2-ecg.log ..\benchdir\v4-3-ecg.log ..\benchdir\v4-1-actor.log ..\benchdir\v4-2-actor.log ..\benchdir\v4-4-actor.log  -t 24h -i 1h -l SyzGPT Syzkaller MoonShine ECG ACTOR -a 3 -T 4.19 -r 'new inputs' 'exec total' -p