import random
import os
from .utils import read_prog
from math import ceil


DEF_PROG1 = '''\
r0 = openat$6lowpan_control(0xffffffffffffff9c, &(0x7f00000000c0), 0x2, 0x0)
ioctl$LOOP_SET_FD(r0, 0x4c00, r0) (fail_nth: 5)
write(r0, &AUTO="01010101", 0x4) (async)'''

DEF_PROG2 = '''\
ptrace$setsig(0x4203, 0x0, 0x0, &(0x7f0000000080)={0x41, 0xb07, 0x10001})
socketpair(0x22, 0x2, 0xf5, &(0x7f0000000100))
bind$tipc(0xffffffffffffffff, 0x0, 0x0)
seccomp$SECCOMP_SET_MODE_FILTER(0x1, 0x0, &(0x7f0000000240)={0x0, &(0x7f0000000200)})
ptrace$setsig(0x4203, 0x0, 0x8, &(0x7f0000000280))
accept(0xffffffffffffffff, &(0x7f0000000500)=@pppol2tp={0x18, 0x1, {0x0, 0xffffffffffffffff, {0x2, 0x0, @loopback}}}, 0x0)
fanotify_init(0x10, 0x800)
syz_clone3(&(0x7f0000001a40)={0x82000, &(0x7f0000001780), &(0x7f00000017c0), 0x0, {0x29}, &(0x7f0000001840)=""/205, 0xcd, &(0x7f0000001940)=""/152, 0x0}, 0x58)'''

DEF_PROG3 = '''\
r0 = openat$bifrost(0xffffffffffffff9c, &AUTO='/dev/bifrost\\x00', 0x2, 0x0)
ioctl$KBASE_IOCTL_VERSION_CHECK(r0, 0xc0048000, &AUTO={0xB, 0xF})
ioctl$KBASE_IOCTL_SET_FLAGS(r0, 0x40048001, &AUTO={0x0})
mmap$bifrost(nil, 0x3000, 0x3, 0x1, r0, 0x3000)
ioctl$KBASE_IOCTL_MEM_ALLOC(r0, 0xc0208005, &AUTO={0x1, 0x1, 0x0, 0xf, 0x0, 0x0})
close(r0)'''

DEF_PROG4 = '''\
r0 = socket$inet_udp(AUTO, AUTO, AUTO)
bind$inet(r0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
r1 = socket$inet_udp(AUTO, AUTO, AUTO)
sendto$inet(r1, &AUTO=""/10, AUTO, 0x0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
recvfrom(r0, &AUTO=""/10, AUTO, 0x0, 0x0, 0x0)'''

DEF_PROG5 = '''\
socketpair(0x0, 0x0, 0x0, &(0x7f0000000140))
socket$kcm(0xa, 0x1, 0x0)
r0 = bpf$MAP_CREATE(0x0, &(0x7f0000000280)={0x12, 0xb, 0x4, 0x800000000000006}, 0x2c)
bpf$MAP_UPDATE_ELEM(0x2, &(0x7f0000000180)={r0, &(0x7f0000000000), &(0x7f0000000140)}, 0x20)
perf_event_open(&(0x7f0000000180)={0x2, 0x70, 0x3e5}, 0x0, 0x0, 0xffffffffffffffff, 0x0)
'''

DEF_PROG6 = '''\
r0 = syz_io_uring_setup(0x7b88, &(0x7f0000000080)={0x0, 0x0, 0x10100}, &(0x7f0000000100)=<r1=>0x0, &(0x7f0000000200)=<r2=>0x0)
r3 = socket$inet_sctp(0x2, 0x5, 0x84)
syz_io_uring_submit(r1, r2, &(0x7f00000001c0)=@IORING_OP_CONNECT={0x10, 0x0, 0x0, r3, 0xb, &(0x7f0000000280)=@in={0x2, 0x0, @local}})
io_uring_enter(r0, 0x291c, 0x0, 0x0, 0x0, 0x0)
'''

# need to expand to 5 or more
DEF_PROGS = [
    {'ioctl$LOOP_SET_FD': DEF_PROG1},
    {'fanotify_init': DEF_PROG2},
    {'mmap$bifrost': DEF_PROG3},
    {'recvfrom': DEF_PROG4},
    {'bpf$MAP_CREATE', DEF_PROG5},
    {'io_uring_enter': DEF_PROG6}
]


DEP_LAYER = 3


def retrieve_progs_randomly(reverse_index, shot=3):
    syscall_names = list(reverse_index.keys())
    random_syscalls = random.sample(syscall_names, shot)
    
    related_progs = []
    for variant in random_syscalls:
        prog_str = search_programs(variant, reverse_index)
        related_progs.append({variant: prog_str})
    
    return related_progs


def retrieve_progs_with_syzdep(syscall, syz_depend, builtin_syscalls, reverse_index, shot=3, covered_calls=[]):
    variant = syscall
    multi_syz_depend = get_multi_layer_depend(variant, syz_depend, 1, DEP_LAYER)
    l1_progs_from_syz, l2_progs_from_syz = random_choose_prog(multi_syz_depend, builtin_syscalls, reverse_index, 1, shot, covered_calls)
    
    l2_offset = ceil(shot / 2)
    related_progs = DEF_PROGS.copy()
    # replace the default progs by l1_progs
    for i, p in enumerate(l1_progs_from_syz):
        if i >= len(related_progs) or i >= shot:
            break
        related_progs[i] = p
    for i, p in enumerate(l2_progs_from_syz):
        if (l2_offset + i) >= len(related_progs) or (l2_offset + i) >= shot:
            break
        related_progs[l2_offset+i] = p
    
    return related_progs[:shot]

def retrieve_progs_with_calldep(syscall, call_depend, builtin_syscalls, reverse_index, shot=3, covered_calls=[]):
    variant = syscall
    multi_call_depend = get_multi_layer_depend(variant, call_depend, 2, DEP_LAYER)
    l1_progs_from_call, l2_progs_from_call = random_choose_prog(multi_call_depend, builtin_syscalls, reverse_index, 2, shot, covered_calls)
    
    l2_offset = ceil(shot / 2)
    related_progs = DEF_PROGS.copy()
    # replace the default progs by l1_progs
    for i, p in enumerate(l1_progs_from_call):
        if i >= len(related_progs) or i >= shot:
            break
        related_progs[i] = p
    for i, p in enumerate(l2_progs_from_call):
        if (l2_offset + i) >= len(related_progs) or (l2_offset + i) >= shot:
            break
        related_progs[l2_offset+i] = p
    
    return related_progs[:shot]

# A bug need to be fixed:
# The sampled related program need to be deduplicated.
# Observe that the third related program is the same as the second.
def retrieve_progs_with_deps(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, shot=3, covered_calls=[]):
    variant = syscall
    multi_syz_depend = get_multi_layer_depend(variant, syz_depend, 1, DEP_LAYER)
    multi_call_depend = get_multi_layer_depend(variant, call_depend, 2, DEP_LAYER)
    
    l1_progs_from_syz, l2_progs_from_syz = random_choose_prog(multi_syz_depend, builtin_syscalls, reverse_index, 1, shot, covered_calls)
    l1_progs_from_call, l2_progs_from_call = random_choose_prog(multi_call_depend, builtin_syscalls, reverse_index, 2, shot, covered_calls)

    related_progs = DEF_PROGS.copy()
    syz_cnt = ceil(shot/2)
    call_cnt = shot - syz_cnt
    l1_syz_cnt = ceil(syz_cnt/2)
    # l2_syz_cnt = syz_cnt - l1_syz_cnt
    l1_call_cnt = ceil(call_cnt/2)
    # l2_call_cnt = call_cnt - l1_call_cnt
    
    # replace the default progs by l1_progs_from_syz
    for i, p in enumerate(l1_progs_from_syz):
        if i >= len(related_progs) or i >= shot:
            break
        related_progs[i] = p
    # start to fill the l2_progs_from_syz at l2_syz_offset (which equals l1_syz_cnt), stop before l1_call_offset
    for i, p in enumerate(l2_progs_from_syz):
        if (l1_syz_cnt+i) >= syz_cnt:
            break
        related_progs[l1_syz_cnt+i] = p
    # start to fill the l1_progs_from_call at l1_call_offset (which equals syz_cnt), filling to the end
    for i, p in enumerate(l1_progs_from_call):
        if (syz_cnt+i) >= len(related_progs) or (syz_cnt+i) >= shot:
            break
        related_progs[syz_cnt+i] = p
    # start to fill the l2_progs_from_call at l2_call_offset (which equals syz_cnt+l1_call_cnt), stop at shot number
    for i, p in enumerate(l2_progs_from_call):
        if (syz_cnt+l1_call_cnt+i) >= len(related_progs) or (syz_cnt+l1_call_cnt+i) >= shot:
            break
        related_progs[syz_cnt+l1_call_cnt+i] = p

    return related_progs[:shot]


def rnd(len):
    return random.randint(0, len-1)


def random_choose_variant(syscalls, builtin_syscalls, covered_calls=[]):
    variants = []
    for syscall in syscalls:
        if syscall in builtin_syscalls:
            l = len(builtin_syscalls[syscall])
            shuf_idx = [i for i in range(l)]
            random.shuffle(shuf_idx)
            for i in shuf_idx:
                v = builtin_syscalls[syscall][i]['Name']
                if covered_calls != [] and v not in covered_calls:
                    continue
                break
            variants.append(v)
    return variants


def get_multi_layer_depend(variant, depends, depend_type=1, n_layer=3):
    # as depended is useless in related selection, so it can be skipped to improve efficiency
    multi_depend = {'depend': {}, 'depended': {}}
    # type 1 for syz_depend, type 2 for call_depend
    if depend_type == 2:
        variant = variant.split('$')[0]

    # layer 1
    if variant in depends:
        multi_depend['depend'][1] = depends[variant]['depend']
        multi_depend['depended'][1] = depends[variant]['depended']
    else:
        multi_depend['depend'][1] = []
        multi_depend['depended'][1] = []
        
    # layer 2~n
    for i in range(2, n_layer+1):
        multi_depend['depend'][i] = []
        for v in multi_depend['depend'][i-1]:
            for d in depends[v]['depend']:
                if d != variant and d not in multi_depend['depend'][i]:
                    multi_depend['depend'][i].append(d)
        multi_depend['depended'][i] = []
        for v in multi_depend['depended'][i-1]:
            for ded in depends[v]['depended']:
                if ded != variant and ded not in multi_depend['depended'][i]:
                    multi_depend['depended'][i].append(ded)
    
    return multi_depend  


def random_choose_prog(multi_depend, builtin_syscalls, reverse_index, depend_type, each_num=2, covered_calls=[]):
    l1_num = len(multi_depend['depend'][1])
    l2_num = len(multi_depend['depend'][2])
    shuf_idx1 = [i for i in range(l1_num)]
    shuf_idx2 = [i for i in range(l2_num)]
    random.shuffle(shuf_idx1)
    random.shuffle(shuf_idx2)

    l1_progs, l2_progs = [], []
    for i in shuf_idx1:
        v = multi_depend['depend'][1][i]
        if depend_type == 2:
            v = random_choose_variant([v], builtin_syscalls, covered_calls)[0]
        if covered_calls != [] and v not in covered_calls:
            continue
        prog_str = search_programs(v, reverse_index)
        if prog_str:
            l1_progs.append({v: prog_str})
        if len(l1_progs) == each_num:
            break
    for i in shuf_idx2:
        v = multi_depend['depend'][2][i]
        if depend_type == 2:
            v = random_choose_variant([v], builtin_syscalls, covered_calls)[0]
        if covered_calls != [] and v not in covered_calls:
            continue
        prog_str = search_programs(v, reverse_index)
        if prog_str:
            l2_progs.append({v: prog_str})
        if len(l2_progs) == each_num:
            break
    return l1_progs, l2_progs


def search_programs(variant, reverse_index):
    try:
        l = len(reverse_index[variant])
        prog_str = read_prog(reverse_index[variant][rnd(l)])
        return prog_str
    except:
        return ''