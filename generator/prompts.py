import random
import os
from math import ceil
from generator.program_retrieval import *


SYS_PROMPT_SYZ_SYNTAX = '''\
Your task is to generate valid Syz programs using the Syzkaller DSL syntax according to my instructions. The Syzkaller DSL is a domain-specific language used for describing sequences of system calls in kernel fuzz testing. It is used in the Syzkaller kernel fuzzer. The syntax for Syz programs is as follows:

line = assignment | call
assignment = variable " = " call
call = syscall-name "(" [arg ["," arg]*] ")"  ["(" [call-prop ["," call-prop*] ")"]
arg = "nil" | "AUTO" | const-arg | resource-arg | result-arg | pointer-arg | string-arg | struct-arg | array-arg | union-arg
const-arg = "0x" hex-integer
resource-arg = variable ["/" hex-integer] ["+" hex-integer]
result-arg = "<" variable "=>" arg
pointer-arg = "&" pointer-arg-addr ["=ANY"] "=" arg
pointer-arg-addr = "AUTO" | "(" pointer-addr ["/" region-size] ")"
string-arg = "'" escaped-string "'" | "\"" escaped-string "\"" | "\"$" escaped-string "\""
struct-arg =  "{" [arg ["," arg]*] "}"
array-arg = "[" [arg ["," arg]*] "]"
union-arg = "@" field-name ["=" arg]
call-prop = prop-name ": " prop-value
variable = "r" dec-integer
pointer-addr = hex-integer
region-size = hex-integer

I have also summarized the Syz program syntax to the following rules:
1. Each line in a Syz program can be either an assignment or a call.
2. Assignments take the form: variable = call
3. Calls specify a syscall to be invoked along with its arguments.
4. Argument types in calls include: nil, AUTO, constant arguments (0x123), resource arguments (variables representing resources), result arguments (variables holding syscall results), pointer arguments (&pointer_addr =ANY= arg), string arguments ('string'), struct arguments ({arg1, arg2}), array arguments ([arg1, arg2]), and union arguments (@field_name = arg).
5. Syz programs can contain blank lines and comments.

Here are some valid Syz program examples:

Example 1:
```syz program
r0 = syz_open_dev$loop(&(0x7f00000011c0), 0x0, 0x0)
r1 = openat$6lowpan_control(0xffffffffffffff9c, &(0x7f00000000c0), 0x2, 0x0)
ioctl$LOOP_SET_FD(r0, 0x4c00, r1)
```

Example 2:
```syz program
r0 = syz_usb_connect$hid(0x0, 0x36, &(0x7f0000000040)=ANY=[@ANYBLOB="12010000000018105e04da07000000000001090224000100000000090400000903000000092100000001222200090581030800000000"], 0x0)
syz_usb_control_io$hid(r0, 0x0, 0x0)
syz_usb_control_io$hid(r0, &(0x7f00000001c0)={0x24, 0x0, 0x0, &(0x7f0000000000)={0x0, 0x22, 0x22, {[@global=@item_012={0x2, 0x1, 0x9, "2313"}, @global=@item_012={0x2, 0x1, 0x0, "e53f"}, @global=@item_4={0x3, 0x1, 0x0, '\f\x00'}, @local=@item_012={0x2, 0x2, 0x2, "9000"}, @global=@item_4={0x3, 0x1, 0x0, "0900be00"}, @main=@item_4={0x3, 0x0, 0x8, '\x00'}, @local=@item_4={0x3, 0x2, 0x0, "09007a15"}, @local=@item_4={0x3, 0x2, 0x0, "5d8c3dda"}]}}, 0x0}, 0x0)
syz_usb_ep_write(r0, 0x81, 0x7, &(0x7f0000000000)='BBBBBBB')
```

Example 3:
```syz program
r0 = openat$6lowpan_control(0xffffffffffffff9c, &(0x7f00000000c0), 0x2, 0x0)
ioctl$LOOP_SET_FD(r0, 0x4c00, r0) (fail_nth: 5)
write(r0, &AUTO="01010101", 0x4) (async)
```

In the following conversation, I will provide the abstract system call sequence and the definition of the related system calls to you. 
Please generate valid Syz programs based on the syntax and only output the Syz program without any other words.'''

SYS_PROMPT_TEST1 = '''\
Your task is to generate valid syz programs. Syz program syntax is a domain-specific language defined by Syzkaller used for describing sequences of sys-calls used in kernel fuzzing.
Please generate valid and rich Syz programs according to the requirements and don't do small talk.'''

USER_PROMPT_TEST1 = '''\
Please generate a comprehensive syz program for fuzzing the syscall "%s". Only output the content of program and avoid any other words like small talk or code comments.'''

SYS_PROMPT_TEST2 = '''\
Your task is to generate valid syz programs. Syz program syntax is a domain-specific language defined by Syzkaller used for describing sequences of sys-calls used in kernel fuzzing. The syz program syntax is as follows:

line = assignment | call
assignment = variable " = " call
call = syscall-name "(" [arg ["," arg]*] ")"  ["(" [call-prop ["," call-prop*] ")"]
arg = "nil" | "AUTO" | const-arg | resource-arg | result-arg | pointer-arg | string-arg | struct-arg | array-arg | union-arg
const-arg = "0x" hex-integer
resource-arg = variable ["/" hex-integer] ["+" hex-integer]
result-arg = "<" variable "=>" arg
pointer-arg = "&" pointer-arg-addr ["=ANY"] "=" arg
pointer-arg-addr = "AUTO" | "(" pointer-addr ["/" region-size] ")"
string-arg = "'" escaped-string "'" | "\"" escaped-string "\"" | "\"$" escaped-string "\""
struct-arg =  "{" [arg ["," arg]*] "}"
array-arg = "[" [arg ["," arg]*] "]"
union-arg = "@" field-name ["=" arg]
call-prop = prop-name ": " prop-value
variable = "r" dec-integer
pointer-addr = hex-integer
region-size = hex-integer

I also summarize the syntax to the following rules:
1. Each line in a Syz program can be either an assignment or a call.
2. Assignments take the form: variable = call
3. Calls specify a syscall to be invoked along with its arguments.
4. Argument types in calls include: nil, AUTO, constant arguments (0x123), resource arguments (variables representing resources), result arguments (variables holding syscall results), pointer arguments (&pointer_addr =ANY= arg), string arguments ('string'), struct arguments ({arg1, arg2}), array arguments ([arg1, arg2]), and union arguments (@field_name = arg).

In the following conversation, I will give you my requirements in the User field. Please generate valid and rich Syz programs according to the requirements and don't do small talk.'''

USER_PROMPT_TEST2 = '''\
Please generate a comprehensive syz program for fuzzing the syscall "%s". Only output the content of program and avoid any other words like small talk or code comments.'''

SYS_PROMPT_TEST3 = '''\
Your task is to generate valid syz programs. Syz program syntax is a domain-specific language defined by Syzkaller used for describing sequences of sys-calls used in kernel fuzzing. The syz program syntax is as follows:

line = assignment | call
assignment = variable " = " call
call = syscall-name "(" [arg ["," arg]*] ")"  ["(" [call-prop ["," call-prop*] ")"]
arg = "nil" | "AUTO" | const-arg | resource-arg | result-arg | pointer-arg | string-arg | struct-arg | array-arg | union-arg
const-arg = "0x" hex-integer
resource-arg = variable ["/" hex-integer] ["+" hex-integer]
result-arg = "<" variable "=>" arg
pointer-arg = "&" pointer-arg-addr ["=ANY"] "=" arg
pointer-arg-addr = "AUTO" | "(" pointer-addr ["/" region-size] ")"
string-arg = "'" escaped-string "'" | "\"" escaped-string "\"" | "\"$" escaped-string "\""
struct-arg =  "{" [arg ["," arg]*] "}"
array-arg = "[" [arg ["," arg]*] "]"
union-arg = "@" field-name ["=" arg]
call-prop = prop-name ": " prop-value
variable = "r" dec-integer
pointer-addr = hex-integer
region-size = hex-integer

I also summarize the syntax to the following rules:
1. Each line in a Syz program can be either an assignment or a call.
2. Assignments take the form: variable = call
3. Calls specify a syscall to be invoked along with its arguments.
4. Argument types in calls include: nil, AUTO, constant arguments (0x123), resource arguments (variables representing resources), result arguments (variables holding syscall results), pointer arguments (&pointer_addr =ANY= arg), string arguments ('string'), struct arguments ({arg1, arg2}), array arguments ([arg1, arg2]), and union arguments (@field_name = arg).

In the following conversation, I will provide you with a few-shot interaction, which contains the tasks from User and the generation from Assistant. Then I will give you my requirements in the User field. Please generate valid and rich Syz programs according to the requirements and don't do small talk.'''

USER_PROMPT_TEST3 = '''\
User: Please generate a comprehensive syz program for fuzzing the syscall "ioctl$BINDER_WRITE_READ". Only output the content of program and avoid any other words like small talk or code comments.
Assistant:
r0 = openat$binderfs(0xffffffffffffff9c, &(0x7f00000000c0)='./binderfs/binder0\x00', 0x0, 0x0)
ioctl$BINDER_SET_CONTEXT_MGR_EXT(r0, AUTO, &AUTO={AUTO, 0x100, 0x0, 0x0})
mmap$binder(&(0x7f00000a0000), 0x2000, 0x1, 0x11, r0, 0x0)
r1 = openat$binderfs(0xffffffffffffff9c, &(0x7f00000000c0)='./binderfs/binder1\x00', 0x0, 0x0)
mmap$binder(&(0x7f00000c0000), 0x2000, 0x1, 0x11, r1, 0x0)
ioctl$BINDER_WRITE_READ(r1, AUTO, &AUTO={AUTO, AUTO, &AUTO=[@transaction_sg={AUTO, {0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, AUTO, AUTO, &AUTO={@flat=@binder={AUTO, 0x0, 0x0, 0x0}, @fd={AUTO, AUTO, r0, AUTO, 0x0}, @ptr={AUTO, 0x0, &AUTO=""/10, AUTO, 0x0, 0x0}}, &AUTO={AUTO, AUTO, AUTO}}, 0x10}], AUTO, AUTO, &AUTO})

User: Please generate a comprehensive syz program for fuzzing the syscall "fanotify_init". Only output the content of program and avoid any other words like small talk or code comments.
Assistant: 
ptrace$setsig(0x4203, 0x0, 0x0, &(0x7f0000000080)={0x41, 0xb07, 0x10001})
socketpair(0x22, 0x2, 0xf5, &(0x7f0000000100))
bind$tipc(0xffffffffffffffff, 0x0, 0x0)
seccomp$SECCOMP_SET_MODE_FILTER(0x1, 0x0, &(0x7f0000000240)={0x0, &(0x7f0000000200)})
ptrace$setsig(0x4203, 0x0, 0x8, &(0x7f0000000280))
accept(0xffffffffffffffff, &(0x7f0000000500)=@pppol2tp={0x18, 0x1, {0x0, 0xffffffffffffffff, {0x2, 0x0, @loopback}}}, 0x0)
fanotify_init(0x10, 0x800)
syz_clone3(&(0x7f0000001a40)={0x82000, &(0x7f0000001780), &(0x7f00000017c0), 0x0, {0x29}, &(0x7f0000001840)=""/205, 0xcd, &(0x7f0000001940)=""/152, 0x0}, 0x58)

User: Please generate a comprehensive syz program for fuzzing the syscall "sendto$inet". Only output the content of program and avoid any other words like small talk or code comments.
Assistant: 
r0 = socket$inet_udp(AUTO, AUTO, AUTO)
bind$inet(r0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
r1 = socket$inet_udp(AUTO, AUTO, AUTO)
sendto$inet(r1, &AUTO=""/10, AUTO, 0x0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
recvfrom(r0, &AUTO=""/10, AUTO, 0x0, 0x0, 0x0)

User: Please generate a comprehensive syz program for fuzzing the syscall "%s". Only output the content of program and avoid any other words like small talk or code comments.
Assistant:'''

SYS_PROMPT_SYZ_SYNTAX_SIMP = '''\
Your task is to generate valid syz programs. Syz program syntax is a domain-specific language defined by Syzkaller used for describing sequences of sys-calls used in kernel fuzzing. The syz program syntax is as follows:

line = assignment | call
assignment = variable " = " call
call = syscall-name "(" [arg ["," arg]*] ")"  ["(" [call-prop ["," call-prop*] ")"]
arg = "nil" | "AUTO" | const-arg | resource-arg | result-arg | pointer-arg | string-arg | struct-arg | array-arg | union-arg
const-arg = "0x" hex-integer
resource-arg = variable ["/" hex-integer] ["+" hex-integer]
result-arg = "<" variable "=>" arg
pointer-arg = "&" pointer-arg-addr ["=ANY"] "=" arg
pointer-arg-addr = "AUTO" | "(" pointer-addr ["/" region-size] ")"
string-arg = "'" escaped-string "'" | "\"" escaped-string "\"" | "\"$" escaped-string "\""
struct-arg =  "{" [arg ["," arg]*] "}"
array-arg = "[" [arg ["," arg]*] "]"
union-arg = "@" field-name ["=" arg]
call-prop = prop-name ": " prop-value
variable = "r" dec-integer
pointer-addr = hex-integer
region-size = hex-integer

I also summarize the syntax to the following rules:
1. Each line in a Syz program can be either an assignment or a call.
2. Assignments take the form: variable = call
3. Calls specify a syscall to be invoked along with its arguments.
4. Argument types in calls include: nil, AUTO, constant arguments (0x123), resource arguments (variables representing resources), result arguments (variables holding syscall results), pointer arguments (&pointer_addr =ANY= arg), string arguments ('string'), struct arguments ({arg1, arg2}), array arguments ([arg1, arg2]), and union arguments (@field_name = arg).

In the following conversation, I will provide you with a few-shot interaction, which contains the tasks from User and the generation from Assistant. Then I will give you my requirements in the User field. Please generate valid and rich Syz programs according to the requirements and don't do small talk.'''

SYS_PROMPT_SYZ_REPAIR_SIMP = '''\
Your task is to repair an invalid Syz programs using the Syzkaller DSL syntax according to my instructions. The Syzkaller DSL is a domain-specific language used for describing sequences of system calls in kernel fuzz testing. It is used in the Syzkaller kernel fuzzer. The syntax for Syz programs is as follows:

line = assignment | call
assignment = variable " = " call
call = syscall-name "(" [arg ["," arg]*] ")"  ["(" [call-prop ["," call-prop*] ")"]
arg = "nil" | "AUTO" | const-arg | resource-arg | result-arg | pointer-arg | string-arg | struct-arg | array-arg | union-arg
const-arg = "0x" hex-integer
resource-arg = variable ["/" hex-integer] ["+" hex-integer]
result-arg = "<" variable "=>" arg
pointer-arg = "&" pointer-arg-addr ["=ANY"] "=" arg
pointer-arg-addr = "AUTO" | "(" pointer-addr ["/" region-size] ")"
string-arg = "'" escaped-string "'" | "\"" escaped-string "\"" | "\"$" escaped-string "\""
struct-arg =  "{" [arg ["," arg]*] "}"
array-arg = "[" [arg ["," arg]*] "]"
union-arg = "@" field-name ["=" arg]
call-prop = prop-name ": " prop-value
variable = "r" dec-integer
pointer-addr = hex-integer
region-size = hex-integer

I have also summarized the Syz program syntax to the following rules:
1. Each line in a Syz program can be either an assignment or a call.
2. Assignments take the form: variable = call
3. Calls specify a syscall to be invoked along with its arguments.
4. Argument types in calls include: nil, AUTO, constant arguments (0x123), resource arguments (variables representing resources), result arguments (variables holding syscall results), pointer arguments (&pointer_addr =ANY= arg), string arguments ('string'), struct arguments ({arg1, arg2}), array arguments ([arg1, arg2]), and union arguments (@field_name = arg).

I will provide you with an invalid Syz program. Please generate valid Syz programs based on the syntax and my requirements.'''

FEWSHOT_PROMPT_GENERATION = '''\
User: Generate a syz program to test the system call "ioctl$BINDER_WRITE_READ", you should consider the memory layout and system call dependencies to ensure that this syz program is valid.
Assistant:
r0 = openat$binderfs(0xffffffffffffff9c, &(0x7f00000000c0)='./binderfs/binder0\x00', 0x0, 0x0)
ioctl$BINDER_SET_CONTEXT_MGR_EXT(r0, AUTO, &AUTO={AUTO, 0x100, 0x0, 0x0})
mmap$binder(&(0x7f00000a0000), 0x2000, 0x1, 0x11, r0, 0x0)
r1 = openat$binderfs(0xffffffffffffff9c, &(0x7f00000000c0)='./binderfs/binder1\x00', 0x0, 0x0)
mmap$binder(&(0x7f00000c0000), 0x2000, 0x1, 0x11, r1, 0x0)
ioctl$BINDER_WRITE_READ(r1, AUTO, &AUTO={AUTO, AUTO, &AUTO=[@transaction_sg={AUTO, {0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, AUTO, AUTO, &AUTO={@flat=@binder={AUTO, 0x0, 0x0, 0x0}, @fd={AUTO, AUTO, r0, AUTO, 0x0}, @ptr={AUTO, 0x0, &AUTO=""/10, AUTO, 0x0, 0x0}}, &AUTO={AUTO, AUTO, AUTO}}, 0x10}], AUTO, AUTO, &AUTO})

User: Generate a syz program to test the system call "fanotify_init", you should consider the memory layout and system call dependencies to ensure that this syz program is valid.
Assistant: 
ptrace$setsig(0x4203, 0x0, 0x0, &(0x7f0000000080)={0x41, 0xb07, 0x10001})
socketpair(0x22, 0x2, 0xf5, &(0x7f0000000100))
bind$tipc(0xffffffffffffffff, 0x0, 0x0)
seccomp$SECCOMP_SET_MODE_FILTER(0x1, 0x0, &(0x7f0000000240)={0x0, &(0x7f0000000200)})
ptrace$setsig(0x4203, 0x0, 0x8, &(0x7f0000000280))
accept(0xffffffffffffffff, &(0x7f0000000500)=@pppol2tp={0x18, 0x1, {0x0, 0xffffffffffffffff, {0x2, 0x0, @loopback}}}, 0x0)
fanotify_init(0x10, 0x800)
syz_clone3(&(0x7f0000001a40)={0x82000, &(0x7f0000001780), &(0x7f00000017c0), 0x0, {0x29}, &(0x7f0000001840)=""/205, 0xcd, &(0x7f0000001940)=""/152, 0x0}, 0x58)

User: Generate a syz program to test the system call "mmap$bifrost", you should consider the memory layout and system call dependencies to ensure that this syz program is valid.
Assistant: 
r0 = openat$bifrost(0xffffffffffffff9c, &AUTO='/dev/bifrost\x00', 0x2, 0x0)
ioctl$KBASE_IOCTL_VERSION_CHECK(r0, 0xc0048000, &AUTO={0xB, 0xF})
ioctl$KBASE_IOCTL_SET_FLAGS(r0, 0x40048001, &AUTO={0x0})
mmap$bifrost(nil, 0x3000, 0x3, 0x1, r0, 0x3000)
ioctl$KBASE_IOCTL_MEM_ALLOC(r0, 0xc0208005, &AUTO={0x1, 0x1, 0x0, 0xf, 0x0, 0x0})
close(r0)

User: Generate a syz program to test the system call "sendto$inet", you should consider the memory layout and system call dependencies to ensure that this syz program is valid.
Assistant: 
r0 = socket$inet_udp(AUTO, AUTO, AUTO)
bind$inet(r0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
r1 = socket$inet_udp(AUTO, AUTO, AUTO)
sendto$inet(r1, &AUTO=""/10, AUTO, 0x0, &AUTO={AUTO, 0x4e20, @empty}, AUTO)
recvfrom(r0, &AUTO=""/10, AUTO, 0x0, 0x0, 0x0)

User: Generate a syz program to test the system call "SYSCALL_PLACEHOLDER", you should consider the memory layout and system call dependencies to ensure that this syz program is valid. APPEND_PLACEHOLDER
Assistant:
'''

SHOT_PROMPT = '''\
User: Please generate a comprehensive syz program for fuzzing the syscall "%s". Refer to the syscall's synopsis and usage, ensuring valid syntax by considering argument types and values. Account for syscall dependencies and argument dependencies to ensure contextual validity. Craft effective interactions among as much relevant and different syscalls as possible to explore deeper Linux kernel states. %s
Assistant:
%s'''

QUERY_TEMPLATE = '''\
%sPlease generate a comprehensive syz program for fuzzing the syscall "%s". Refer to the syscall's synopsis and usage, ensuring valid syntax by considering argument types and values. Account for syscall dependencies and argument dependencies to ensure contextual validity. Craft effective interactions among as much relevant and different syscalls as possible to explore deeper Linux kernel states. %s'''

EXTRA_REQ = '''\
REMEMBER the generated program must at least contain target syscall %s. AVOID endless repetitive syscall invokations. Only output the program and avoid any other words like small talk or explainations.'''

SIMP_EXTRA_REQ = '''\
Only output the program and avoid any other words like small talk or explainations.'''


def gen_msg_and_query(target, related_progs, extra_context='', extra_requirements='', sys_prompt=''):
    msg = [{"role": "system", "content": sys_prompt}]
    legacy_query = ''
    for p in related_progs:
        variant = list(p.keys())[0]
        prog_str = p[variant].strip()
        msg.append({"role": "user", "content": QUERY_TEMPLATE%('', variant, '')})
        msg.append({"role": "assistant", "content": prog_str})
        legacy_query += SHOT_PROMPT%(variant, '', prog_str) + '\n\n'
    query = QUERY_TEMPLATE%(extra_context, target, extra_requirements)
    legacy_query += SHOT_PROMPT%(target, EXTRA_REQ%target, '')
    return msg, query, legacy_query


def prev_progs_as_context(target, prev_progs):
    if len(prev_progs) == 0:
        return ''
    context = '''\
In the previous program generation task for syscall %s, your generation is:

%s

But the program failed to pass the syntax check or did not bring new coverage in fuzzing. Take it as failure experience for this task: '''%(target, prev_progs[-1])
    return context



def GEN_WITH_RANDOM(syscall, reverse_index, shot, prev_progs=[]):
    related_progs = retrieve_progs_randomly(reverse_index, shot)
    context = prev_progs_as_context(syscall, prev_progs)
    return gen_msg_and_query(target=syscall, related_progs=related_progs, extra_context=context, extra_requirements=EXTRA_REQ%syscall, sys_prompt=SYS_PROMPT_SYZ_SYNTAX_SIMP)


def GEN_WITH_FIXED(syscall, shot, prev_progs=[]):
    related_progs = DEF_PROGS.copy()[:shot]
    context = prev_progs_as_context(syscall, prev_progs)
    return gen_msg_and_query(target=syscall, related_progs=related_progs, extra_context=context, extra_requirements=EXTRA_REQ%syscall, sys_prompt=SYS_PROMPT_SYZ_SYNTAX_SIMP)


def GEN_WITH_DIRECT(syscall):
    return gen_msg_and_query(target=syscall, related_progs=[], extra_context='', extra_requirements=SIMP_EXTRA_REQ, sys_prompt='')


def GEN_WITH_SYZDEP(syscall, syz_depend, builtin_syscalls, reverse_index, shot=3, covered_calls=[], prev_progs=[]):
    related_progs = retrieve_progs_with_syzdep(syscall, syz_depend, builtin_syscalls, reverse_index, shot, covered_calls)
    context = prev_progs_as_context(syscall, prev_progs)
    return gen_msg_and_query(target=syscall, related_progs=related_progs, extra_context=context, extra_requirements=EXTRA_REQ%syscall, sys_prompt=SYS_PROMPT_SYZ_SYNTAX_SIMP)


def GEN_WITH_CALLDEP(syscall, call_depend, builtin_syscalls, reverse_index, shot=3, covered_calls=[], prev_progs=[]):
    related_progs = retrieve_progs_with_calldep(syscall, call_depend, builtin_syscalls, reverse_index, shot, covered_calls)
    context = prev_progs_as_context(syscall, prev_progs)
    return gen_msg_and_query(target=syscall, related_progs=related_progs, extra_context=context, extra_requirements=EXTRA_REQ%syscall, sys_prompt=SYS_PROMPT_SYZ_SYNTAX_SIMP)


# A bug need to be fixed:
# The sampled related program need to be deduplicated.
# Observe that the third related program is the same as the second.
def GEN_WITH_DEPS(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, shot=3, covered_calls=[], prev_progs=[]):
    related_progs = retrieve_progs_with_deps(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, shot, covered_calls)
    context = prev_progs_as_context(syscall, prev_progs)
    return gen_msg_and_query(target=syscall, related_progs=related_progs, extra_context=context, extra_requirements=EXTRA_REQ%syscall, sys_prompt=SYS_PROMPT_SYZ_SYNTAX_SIMP)


def GEN_WITH_DEPS_NOSYS(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, shot=3, covered_calls=[], prev_progs=[]):
    related_progs = retrieve_progs_with_deps(syscall, call_depend, syz_depend, builtin_syscalls, reverse_index, shot, covered_calls)
    context = prev_progs_as_context(syscall, prev_progs)
    return gen_msg_and_query(target=syscall, related_progs=related_progs, extra_context=context, extra_requirements=EXTRA_REQ%syscall, sys_prompt='')

