import argparse
import concurrent.futures
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from time import time

YES = '[b green]y'
NO = '[b red]n'
NONE = '[bwhite]-'
ERROR = '[b pink]X'


def parse_config(conf_path):
    conf = {}
    with open(conf_path, "r") as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith('#'):
            continue
        spls = line.split('=')
        if len(spls) != 2:
            continue
        if spls[0] in conf:
            print('[WARNING] multiple CONFIG: %s'%spls[0])
        else:
            conf.setdefault(spls[0], spls[1].strip())
    
    return conf
    

def parse_opt(opt):
    if opt == 'y':
        return YES
    elif opt == 'n':
        return NO
    else:
        return '[b purple]%s'%opt
    


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='diff two .config')
    parser.add_argument('conf1', type=str, help='path to .config 1')
    parser.add_argument('conf2', type=str, help='path to .config 2')
    parser.add_argument('-c', '--col_name', type=str, nargs='+', help='column names')
    parser.add_argument('-v', '--verbose', action='store_true', help='show verbose output')
    args = parser.parse_args()

    start_time = time()
    console = Console()
    
    if args.col_name and len(args.col_name) == 2:
        col1_name, col2_name = args.col_name[0], args.col_name[1]
    else:
        col1_name, col2_name = '.config 1', '.config 2'


    with console.status("Comparing two config files ...\n", spinner="earth"):
        # conf1 = parse_config(args.conf1)
        # conf2 = parse_config(args.conf2)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future1 = executor.submit(parse_config, args.conf1)
            future2 = executor.submit(parse_config, args.conf2)

        conf1 = future1.result()
        conf2 = future2.result()

        uniq1 = conf1.keys() - conf2.keys()
        uniq2 = conf2.keys() - conf1.keys()
        common = conf1.keys() & conf2.keys()

        table = Table(
            title='Kernel Config Comparison', 
            caption='Caption: y for yes, n for no, - for none',
            caption_style='b i white',
            # expand=True,
            show_edge=True
            # show_lines=True,
            # leading=True
        )

        table.add_column("Kernel Config Option", justify='left')
        table.add_column(col1_name, justify='center')
        table.add_column(col2_name, justify='center')


        for k in uniq1:
            table.add_row('[yellow]%s'%k, parse_opt(conf1[k]), NONE)

        for k in uniq2:
            table.add_row('[yellow]%s'%k, NONE, parse_opt(conf2[k]))
        
        cnt = 0
        for k in common:
            v1, v2 = conf1[k], conf2[k]
            if v1 != v2:
                cnt += 1
                table.add_row('[b yellow]%s'%k, parse_opt(v1), parse_opt(v2))

        console.print(table)

    console.print(Panel('[b]Comparison finished! Cost %.2f seconds.[/]\n\
[b]config 1[/]: %s\n\
[b]config 2[/]: %s\n\
There are [b blue]%d[/] unique options in [b]config 1[/], [b cyan]%d[/] unique options in [b]config 2[/], \
and [b yellow]%d[/] common options with different values.'%((time()-start_time), args.conf1, args.conf2, len(uniq1), len(uniq2), cnt)))