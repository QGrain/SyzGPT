import json
import os
from time import time


def check_dir(d):
    if os.path.isdir(d):
        return True
    else:
        try:
            os.makedirs(d)
            return True
        except:
            return False


def build_arg_map(d_all):
    # fortmat dict{'key':set()}
    
    black_list = ['int8', 'int16', 'int32', 'int64', 'intptr', 'array', 'len', 'buffer', 'const', 'bytesize',
                  'send_flags', 'mount_flags', 'open_flags', 'fs_options', 
                  'drm_pvr_srvkm_cmd']
    
    d_out = {}
    d_in = {}
    for syscall in d_all:
        for d_call in d_all[syscall]:
            ret = d_call["Return"]
            call_name = d_call["Name"]
            
            # build out_dict according to mapping of return_args->syscall_variants
            if ret != None:
                if ret in black_list:
                    print('[DEBUG] call->ret: %s->%s is in black_list'%(call_name, ret))
                if ret not in d_out:
                    d_out[ret] = set([call_name])
                else:
                    d_out[ret].add(call_name)
            
            for arg_key in d_call["Args"]:
                arg = d_call["Args"][arg_key]
                direc, new_arg = parse_arg(arg)
                
                # skip the args containing black_list type
                skip = 0
                for black in black_list:
                    if black in new_arg:
                        skip = 1
                        break
                if skip == 1:
                    continue
                
                # complete out_dict according to mapping of out_args->syscall_variants
                if direc == 'out' or direc == 'inout':
                    if new_arg not in d_out:
                        d_out[new_arg] = set([call_name])
                    else:
                        d_out[new_arg].add(call_name)
                # build in_dict according to mapping of in_args->syscall_variants
                if direc == 'in' or direc == 'inout' or direc == None:
                    if new_arg not in d_in:
                        d_in[new_arg] = set([call_name])
                    else:
                        d_in[new_arg].add(call_name)
    return (d_out, d_in)


def parse_arg(arg):
    direction = None
    new_arg = arg
    def_direction = ['in', 'out', 'inout']
    for direc in def_direction:
        direc_filter = direc+', '
        if direc_filter in arg:
            new_arg = arg.split(direc_filter)[1]
            new_arg = new_arg.split(']')[0].split('[')[0]
            direction = direc
    return (direction, new_arg)


def extract_in_depend_out(d_depend, d_out, d_in):
    # format of d_depend: {'call': [depended_call, ...]}
    for in_arg in d_in:
        if in_arg not in d_out:
            continue
        for call in d_in[in_arg]:
            if call not in d_depend:
                d_depend[call] = d_out[in_arg]
            else:
                d_depend[call] = d_depend[call] | d_out[in_arg]
    return d_depend


def extract_in_depend_in(d_depend, d_in):
    d = {}
    for in_arg in d_in:
        for call in d_in[in_arg]:
            tmp = []
            for c in d_in[in_arg]:
                if c == call:
                    continue
                tmp.append(c)
            if call not in d:
                d[call] = set(tmp)
            else:
                d[call] = d[call] | set(tmp)
    for call in d:
        if call not in d_depend:
            d_depend[call] = d[call]
        else:
            d_depend[call] = d_depend[call] | d[call]


def parse_depended(d_depend):
    '''
    format of d_all: {
        'call': {
            'depend': set([depend_call, ...]),
            'depended': set([depended_call, ...])
        },
        ...
    }
    '''
    d_all = {}
    d_depended = {}
    for call in d_depend:
        d_all[call] = {'depend': set([]), 'depended': set([])}
        for c in d_depend[call]:
            if c not in d_all:
                d_all[c] = {'depend': set([]), 'depended': set([])}
            if c not in d_depended:
                d_depended[c] = set([call])
            else:
                d_depended[c] = d_depended[c] | set([call])
    
    for call in d_all:
        if call in d_depend:
            d_all[call]['depend'] = d_depend[call]
        else:
            d_all[call]['depend'] = set([])
        if call in d_depended:
            d_all[call]['depended'] = d_depended[call]
        else:
            d_all[call]['depended'] = set([])
    
    return d_all


def recur_search_depend(d_depend, call, depth=1):
    if depth == 1:
        if call in d_depend:
            return d_depend[call]
        else:
            return set()
    s = set()
    if call in d_depend:
        for c in d_depend[call]:
            s = s | recur_search_depend(d_depend, c, depth-1)
    return s


def depend_set2list(d):
    for c in d:
        d[c]['depend'] = list(d[c]['depend'])
        d[c]['depended'] = list(d[c]['depended'])


def extract_dependencies():
    t0 = time()
    with open('../data/builtin_syscalls.json', 'r') as f:
        builtin_syscalls = json.load(f)
    print('[%.2fs] load builtin_syscalls'%(time()-t0))
    
    d_out, d_in = build_arg_map(builtin_syscalls)
    print('[%.2fs] build_arg_map'%(time()-t0))
    print('\n============================= len(d_out)=%d ============================='%(len(d_out)))
    for arg in d_out:
        l = len(d_out[arg])
        if l < 50:
            pass
            # print('[out] len(%s)=%d:'%(arg, l), d_out[arg])
        else:
            print('[out] len(%s)=%d, this may be a common type'%(arg, l))
    
    print('\n============================= len(d_in)=%d ============================='%(len(d_in)))
    for arg in d_in:
        l = len(d_in[arg])
        if l < 50:
            pass
            # print('[in] len(%s)=%d:'%(arg, l), d_in[arg])
        else:
            print('[in] len(%s)=%d, this may be a common type'%(arg, l))
    print('[%.2fs] done with len(d_out)=%d, len(d_in)=%d!'%(time()-t0, len(d_out), len(d_in)))

    d_depend = {}
    extract_in_depend_out(d_depend, d_out, d_in)
    d_depend_inout = d_depend.copy()
    extract_in_depend_in(d_depend, d_in)
    
    print('\n============================= len(d_depend)=%d ============================='%(len(d_depend)))
    # for call in d_depend:
    #     for c in ['accept', 'select', 'poll', 'socket', 'fcntl']:
    #         if c == call:
    #             s = recur_search_depend(d_depend, call, 1)
    #             print('%s depends on %d calls:'%(call, len(d_depend[call])), d_depend[call])
    #             print('depth 3 depends:', s)
    print('[%.2fs] done with len(d_depend)=%d!'%(time()-t0, len(d_depend)))
    assert(d_depend_inout != d_depend)
    return (d_depend_inout, d_depend)

if __name__ == '__main__':
    d_depend_inout, d_depend_inout_inin = extract_dependencies()
    d_depend_inout_all, d_depend_inout_inin_all = parse_depended(d_depend_inout), parse_depended(d_depend_inout_inin)
    depend_set2list(d_depend_inout_all)
    depend_set2list(d_depend_inout_inin_all)
    
    # save the dependencies
    check_dir('./results')
    with open('./results/syz_depend_inout.json', 'w') as f:
        json.dump(d_depend_inout_all, f, indent=4)

    with open('./results/syz_depend_inout_inin.json', 'w') as f:
        json.dump(d_depend_inout_inin_all, f, indent=4)
    print('\nSave to ./results/')