import argparse
import os
from time import time


def load_builtin_syscalls():
    project_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    builtin_data_dir = os.path.join(project_dir, 'data', 'covered')
    
    with open(os.path.join(builtin_data_dir, 'builtin_syscalls.txt'), 'r') as f:
        builtin_syscalls = [line.strip() for line in f.readlines()]
    
    with open(os.path.join(builtin_data_dir, 'builtin_variants.txt'), 'r') as f:
        builtin_variants = [line.strip() for line in f.readlines()]
    return builtin_syscalls, builtin_variants


def read_covered_calls(path):
    with open(path, 'r') as f:
        covered_variants = [line.strip() for line in f.readlines()]
    covered_syscalls = [variant.split('$')[0] for variant in covered_variants]
    return covered_syscalls, covered_variants


def stat_common(covered_list):
    if len(covered_list) == 0:
        return []

    common = set(covered_list[0])
    for i in range(1, len(covered_list)):
        common = common.intersection(set(covered_list[i]))
    return list(common)


def stat_uncovered(covered_list, builtin):
    if len(covered_list) == 0:
        return []
    
    builtin_set = set(builtin)
    uncovered = builtin_set.difference(set(covered_list[0]))
    for i in range(1, len(covered_list)):
        uncovered = uncovered.intersection(builtin_set.difference(set(covered_list[i])))
    return list(uncovered)


def find_workdirs(paths):
    workdir_list = []
    for path in paths:
        for root, dirs, _ in os.walk(path):
            for d in dirs:
                if d == 'crashes':
                    workdir_list.append(root)
                    break
    return workdir_list


def stat_lfsc(paths, builtin_syscalls, builtin_variants):
    covered_syscalls_list, covered_variants_list = [], []
    for path in paths:
        covered_syscalls, covered_variants = read_covered_calls(path)
        covered_syscalls_list.append(covered_syscalls)
        covered_variants_list.append(covered_variants)
    
    common_syscalls = stat_common(covered_syscalls_list)
    common_variants = stat_common(covered_variants_list)   
    uncovered_syscalls = stat_uncovered(covered_syscalls_list, builtin_syscalls)
    uncovered_variants = stat_uncovered(covered_variants_list, builtin_variants)

    return common_syscalls, common_variants, uncovered_syscalls, uncovered_variants

def print_t(s, t0):
    print('[%.2fs] %s'%(time()-t0, s))


if __name__ == '__main__':
    t0 = time()
    parser = argparse.ArgumentParser(description='Analyze bug distribution')
    parser.add_argument('-D', '--base_workdirs', type=str, nargs= '+', help='path to the base workdirs containing different fuzzer workdirs')
    parser.add_argument('-C', '--coveredcalls_paths', type=str, nargs= '+', help='path to the CoveredCalls')
    parser.add_argument('-e', '--enabledcalls_path', type=str, help='path to the enabled calls in workdir')
    # parser.add_argument('-H', '--hash', type=str, help='hash of the crash (length is at least 7)')
    # parser.add_argument('-f', '--flush_cache', action='store_true', help='flush cache and re-fetch the reports')
    args = parser.parse_args()
    
    if args.coveredcalls_paths:
        builtin_syscalls, builtin_variants = load_builtin_syscalls()
        if args.enabledcalls_path:
            with open(args.enabledcalls_path, 'r') as f:
                builtin_variants = [line.strip() for line in f.readlines()]
        
        com_calls_num, com_vars_num, unc_calls_num, unc_vars_num, uns_calls_num, uns_vars_num = [], [], [], [], [], []
        coveredcalls_paths = list(args.coveredcalls_paths)
        for i in range(1, len(coveredcalls_paths)+1):
            com_calls, com_vars, unc_calls, unc_vars = stat_lfsc(coveredcalls_paths[:i], builtin_syscalls, builtin_variants)
            com_calls_num.append(len(com_calls))
            com_vars_num.append(len(com_vars))
            unc_calls_num.append(len(unc_calls))
            unc_vars_num.append(len(unc_vars))
            uns_calls_num.append(len(builtin_syscalls)-len(com_calls)-len(unc_calls))
            uns_vars_num.append(len(builtin_variants)-len(com_vars)-len(unc_vars))
        
        print_t('builtin syscalls: %d'%(len(builtin_syscalls)), t0)
        print_t('builtin variants: %d'%(len(builtin_variants)), t0)
        print_t('common syscalls: %d'%(len(com_calls)), t0)
        print_t('common variants: %d'%(len(com_vars)), t0)
        print_t('uncovered syscalls: %d'%(len(unc_calls)), t0)
        print_t('uncovered variants: %d'%(len(unc_vars)), t0)
        print_t('unstably covered syscalls: %d'%(len(builtin_syscalls)-len(com_calls)-len(unc_calls)), t0)
        print_t('unstably covered variants: %d'%(len(builtin_variants)-len(com_vars)-len(unc_vars)), t0)
        
        # print data  for plot
        print('common_syscalls =', com_calls_num)
        print('common_variants =', com_vars_num)
        print('uncovered_syscalls =', unc_calls_num)
        print('uncovered_variants =', unc_vars_num)
        print('unstable_syscalls =', uns_calls_num)
        print('unstable_variants =', uns_vars_num)

        if args.enabledcalls_path:
            with open('uncovered_variants_%d_avg.txt'%len(args.coveredcalls_paths), 'w') as f:
                for v in unc_vars:
                    f.write('%s\n'%v)

    if args.base_workdirs:
        workdir_list = find_workdirs(args.base_workdirs)
        crashdir_list = [os.path.join(workdir, 'crashes') for workdir in workdir_list]
    
    print_t('Done!', t0)