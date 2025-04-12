SYSTEM_PROMPT_GENERATE = '''\
I will provide the detailed Linux manual page for a specific Linux system call I want to discuss. Analyze this information, identify any explicit and implicit \
dependencies with other Linux system calls, and also search for any related system calls mentioned in the information I give you, using your knowledge of Linux \
manual page: section 2, analyze the manual pages of related system calls, to determine their dependencies with the specific Linux system call I want to discuss. \
Finally, provide me with a list of all system calls involved in explicit and implicit dependencies for the specified system call specific system call I want to discuss.\
YOU MUST KEEP IN MIND: 1. a system call must have dependencies, it either depend on other system calls, or be depended upon by other system calls. 2. Each system call \
can only appear at most once in the result! NEVER generate repeated system calls! For system calls in the information I give you that appear in the form like "set*uid()," \
you should replace the possible "*" values based on your knowledge of Linux system calls and Linux manual page: section 2. Taking "set*uid" as an example, it can be replaced \
with "seteuid(2), setfsuid(2), setuid(2), setresuid(2), setreuid(2)" from Linux manual page: section 2. Therefore, if you need to output the system call "set*uid," you should \
not directly output "set*uid" but instead output "seteuid, setfsuid, setuid, setresuid, setreuid." Linux system calls have explicit and implicit dependencies, which are also \
Linux system calls. The explicit and implicit dependencies between system calls can vary in Linux, depending on the specific system calls and their functionalities. Here are \
some examples of explicit and implicit dependencies: 1. Explicit: Explicit dependencies between system calls are those where one system call directly relies on the result or \
output of another, or one system call can be used after another system call. Here are some examples: select(2), poll(2), epoll(2) and accept(2): In the Linux manual page of \
system call "accept(2)", it says "In order to be notified of incoming connections on a socket, you can use select(2), poll(2), or epoll(7).  A readable event will be delivered \
when a new connection is attempted and you may then call accept() to get a socket for that connection." The manual page tells the sequence of system calls: "accept" can be \
called AFTER the system calls "select", "poll", and "epoll", which means the system call "accept" explicitly depend on the system call "select", "poll", and "epoll". It also \
means system call "select", "poll", and "epoll" are explicitly depended upon by "accept". fork(2) and execve(2):  In the manual page of "execve(2)", it says: "This kernel logic \
ensures that the RLIMIT_NPROC resource limit is still enforced for the common privileged daemon workflow—namely, fork(2) + set*uid() + execve()." It tells the sequence of \
"fork(2) + set*uid() + execve()", which means the system call "execve" can be used AFTER "fork", thus "execve" explicitly depend on the system call "fork". open(2) and close(2): \
In the manual page of "close(2)", it says: "int close(int fd);". It means "fd" is the parameter of system call "close", and you should know that "fd" (file descriptor) is \
obtained from system call "open". So the system call "close" explicitly depend on "open", and "open" is explicitly depended upon by "close". 2. Implicit: Implicit dependencies \
between system calls are not as direct as explicit dependencies but still exist due to the overall behavior and state of the system. These dependencies can be harder to identify \
but are crucial to understanding system call interactions. Some examples include: gettid(2) and capget(2): In the manual page of "capget(2)", it says: "That is, on kernels that \
have VFS capabilities support, when calling capset(), the only permitted values for hdrp->pid are 0 or, equivalently, the value returned by gettid(2)." You must learn from it \
that "capget" can depend on the return value of "gettid", so the system call "capget" implicitly depend on the system call "gettid", and the system call "gettid" is implicitly \
depended upon by the system call "capget". mmap(2), shmat(2) and futex(2): In the Linux manual page of "futex(2)", it says: "In order to share a futex between processes, the \
futex is placed in a region of shared memory, created using (for example) mmap(2) or shmat(2)." You must learn from it that the system call "futex" must depend on the memory \
created by "mmap" or "shmat", which means "futex" implicitly depend on the system call "mmap" and "shmat". pipe(2) and dup2(2): If I give you the Linux manual page of system \
call "dup2", you probably cannot learn from it the dependency between "dup" (or "dup2" or "dup3") and other system calls. However, you MUST use your knowledge of Linux system \
calls and Linux manual page section 2, and you can know that "pipe" and "dup" can be used together to achieve interprocess communication and I/O redirection. A common usage is \
to create a child process, close its standard input (file descriptor 0), associate the read end of a pipe with the child process\'s standard input, and then close the \
corresponding end of the pipe in the parent process while writing data into the child process\'s standard input. In this case, code sequence is like "int pipefd[2]; pipe(pipefd); \
dup2(pipefd[0], 0);". Therefore, when I give you the Linux manual page of "dup", you should use your knowledge, and tell me that system call "dup" implicitly depend on system \
call "pipe". I need you to generate dependencies of system calls and output the results in json format without any other unrelated words. '''

SYSTEM_PROMPT_CONDENSE = '''\
As an expert of Natural Language Processing and Linux Kernel, your role will be to condense the provided text to save the tokens. Please ensure that key information is retained, \
such as which variables the system call operates on and what dependencies exist when using the system call. YOU MUST NEVER condense sentences related to system calls. \
If a sentence contains a specific system call, please do not modify it and keep it as it is. You should always remember that the format of a system call is "xxx(2)" or "xxx()". \
If you encounter a word with 2 inside parentheses, you should recognize it as a system call. Output the condensed text without any other words.'''

SYSTEM_PROMPT_FREE_GEN_FROM_LIST = '''Linux system calls have explicit and implicit dependencies, which are also Linux system calls. The explicit and implicit dependencies between system calls \
can vary in Linux, depending on the specific system calls and their functionalities. YOU MUST KEEP IN MIND: One system call must have dependencies, it either depend on other \
system calls, or be depended upon by other system calls. Here are some examples of explicit and implicit dependencies: Explicit: Explicit dependencies between system calls are \
those where one system call directly relies on the result or output of another, or one system call can be used after another system call. Here are some examples: select(2), \
poll(2), epoll(2) and accept(2): In the Linux manual page of system call "accept(2)", it says "In order to be notified of incoming connections on a socket, you can use select(2), \
poll(2), or epoll(7).  A readable event will be delivered when a new connection is attempted and you may then call accept() to get a socket for that connection." \
The manual page tells the sequence of system calls: "accept" can be called AFTER the system calls "select", "poll", and "epoll", which means the system call "accept" explicitly \
depend on the system call "select", "poll", and "epoll". It also means system call "select", "poll", and "epoll" are explicitly depended upon by "accept". fork(2) and execve(2): \
In the manual page of "execve(2)", it says: "This kernel logic ensures that the RLIMIT_NPROC resource limit is still enforced for the common privileged daemon workflow—namely, \
fork(2) + set*uid() + execve()." It tells the sequence of "fork(2) + set*uid() + execve()", which means the system call "execve" can be used AFTER "fork", thus "execve" explicitly \
depend on the system call "fork". open(2) and close(2): In the manual page of "close(2)", it says: "int close(int fd);". It means "fd" is the parameter of system call "close", \
and you should know that "fd" (file descriptor) is obtained from system call "open". So the system call "close" explicitly depend on "open", and "open" is explicitly depended \
upon by "close". Implicit: Implicit dependencies between system calls are not as direct as explicit dependencies but still exist due to the overall behavior and state of the system. \
These dependencies can be harder to identify but are crucial to understanding system call interactions. Some examples include: gettid(2) and capget(2): In the manual page of "capget(2)", \
it says: "That is, on kernels that have VFS capabilities support, when calling capset(), the only permitted values for hdrp->pid are 0 or, equivalently, the value returned by gettid(2)." \
You must learn from it that "capget" can depend on the return value of "gettid", so the system call "capget" implicitly depend on the system call "gettid", and the system call "gettid" \
is implicitly depended upon by the system call "capget". mmap(2), shmat(2) and futex(2): In the Linux manual page of "futex(2)", it says: "In order to share a futex between processes, \
the futex is placed in a region of shared memory, created using (for example) mmap(2) or shmat(2)." You must learn from it that the system call "futex" must depend on the memory \
created by "mmap" or "shmat", which means "futex" implicitly depend on the system call "mmap" and "shmat". pipe(2) and dup2(2): If I give you the Linux manual page of system call "dup2", \
you probably cannot learn from it the dependency between "dup" (or "dup2" or "dup3") and other system calls. However, you MUST use your knowledge of Linux system calls and Linux manual \
page section 2, and you can know that "pipe" and "dup" can be used together to achieve interprocess communication and I/O redirection. A common usage is to create a child process, \
close its standard input (file descriptor 0), associate the read end of a pipe with the child process\'s standard input, and then close the corresponding end of the pipe in the \
parent process while writing data into the child process\'s standard input. In this case, code sequence is like "int pipefd[2]; pipe(pipefd); dup2(pipefd[0], 0);". Therefore, \
when I give you the Linux manual page of "dup", you should use your knowledge, and tell me that system call "dup" implicitly depend on system call "pipe". Now you know what \
are explicit and implicit dependencies, and you know the meanings of "a system call depend on another system call" and "a system call is depended upon by another system call". \
You must use your knowledge of Linux manual pages of system calls and your knowledge of the usage of all Linux system calls to generate the dependencies of system calls. \
I will give you the name of a Linux system call, and you must use your knowledge of how this system call could be used with other system calls to tell me: what system calls \
does this system call depend on and what system calls is this system call depended upon by? I will give you a preliminary list of system calls which have dependencies with \
a certain system call , and this list is manually extracted from the Linux manual page document. This list probably have some incorrect or repeated results of system call \
dependencies! You must use your knowledge to check it and correct it! This list shows What system calls does the certain system call explicitly and implicitly depend on, \
and what system calls is this system call explicitly and implicitly depended upon by. The format of this list is "explicit depend: xxx \n implicit depend: xxx \n explic depended: xxx \n implicit depended: xxx \n", \
the "xxx" are Linux system calls, if there are more than one, they are linked with ", "; if there is none, "xxx" is "null". The dependency relationships presented in this \
list may not be accurate. With this preliminary list, use your knowledge of Linux manual pages of system calls and your knowledge of the usage of all Linux system calls \
to further associate and analogize to discover more system call dependencies. You must: 1. If the preliminary list includes the same repeated system call in different \
categories, please determine the correct category for that system call and keep it only in the correct category, removing it from other categories where it appears. \
If a system call appear more than once in the list I give you, this system call is illegal! One system call MUST ONLY appear once in the result! The same system call \
CANNOT appear more than once in the same or in the different categories!(for example: system call "open" must not appear in "explicit depend" and "explicit depended" at the same time!) \
2. Organize this preliminary list. If there are system calls that are categorized incorrectly, please reclassify them into the correct category. 3. Based on your knowledge, \
understand how this system call should be used and with which other system calls it can be used. Try to identify more correct system call dependency relationships \
(e.g., "dup" implicitly depends on the system call "pipe") and merge the new results into my original list. YOU MUST KEEP IN MIND: each system call can only appear \
at most once in the result!!! NEVER generate repeated system calls! Your answers MUST output the results in json format without any other unrelated words. '''

SYSTEM_PROMPT_FREE_GEN_FROM_NULL = '''Linux system calls have explicit and implicit dependencies, which are also Linux system calls. The explicit and implicit dependencies between system calls \
can vary in Linux, depending on the specific system calls and their functionalities. YOU MUST KEEP IN MIND: One system call must have dependencies, it either depend on other \
system calls, or be depended upon by other system calls. Here are some examples of explicit and implicit dependencies: Explicit: Explicit dependencies between system calls are \
those where one system call directly relies on the result or output of another, or one system call can be used after another system call. Here are some examples: select(2), \
poll(2), epoll(2) and accept(2): In the Linux manual page of system call "accept(2)", it says "In order to be notified of incoming connections on a socket, you can use select(2), \
poll(2), or epoll(7).  A readable event will be delivered when a new connection is attempted and you may then call accept() to get a socket for that connection." \
The manual page tells the sequence of system calls: "accept" can be called AFTER the system calls "select", "poll", and "epoll", which means the system call "accept" explicitly \
depend on the system call "select", "poll", and "epoll". It also means system call "select", "poll", and "epoll" are explicitly depended upon by "accept". fork(2) and execve(2): \
In the manual page of "execve(2)", it says: "This kernel logic ensures that the RLIMIT_NPROC resource limit is still enforced for the common privileged daemon workflow—namely, \
fork(2) + set*uid() + execve()." It tells the sequence of "fork(2) + set*uid() + execve()", which means the system call "execve" can be used AFTER "fork", thus "execve" explicitly \
depend on the system call "fork". open(2) and close(2): In the manual page of "close(2)", it says: "int close(int fd);". It means "fd" is the parameter of system call "close", \
and you should know that "fd" (file descriptor) is obtained from system call "open". So the system call "close" explicitly depend on "open", and "open" is explicitly depended \
upon by "close". Implicit: Implicit dependencies between system calls are not as direct as explicit dependencies but still exist due to the overall behavior and state of the system. \
These dependencies can be harder to identify but are crucial to understanding system call interactions. Some examples include: gettid(2) and capget(2): In the manual page of "capget(2)", \
it says: "That is, on kernels that have VFS capabilities support, when calling capset(), the only permitted values for hdrp->pid are 0 or, equivalently, the value returned by gettid(2)." \
You must learn from it that "capget" can depend on the return value of "gettid", so the system call "capget" implicitly depend on the system call "gettid", and the system call "gettid" \
is implicitly depended upon by the system call "capget". mmap(2), shmat(2) and futex(2): In the Linux manual page of "futex(2)", it says: "In order to share a futex between processes, \
the futex is placed in a region of shared memory, created using (for example) mmap(2) or shmat(2)." You must learn from it that the system call "futex" must depend on the memory \
created by "mmap" or "shmat", which means "futex" implicitly depend on the system call "mmap" and "shmat". pipe(2) and dup2(2): If I give you the Linux manual page of system call "dup2", \
you probably cannot learn from it the dependency between "dup" (or "dup2" or "dup3") and other system calls. However, you MUST use your knowledge of Linux system calls and Linux manual \
page section 2, and you can know that "pipe" and "dup" can be used together to achieve interprocess communication and I/O redirection. A common usage is to create a child process, \
close its standard input (file descriptor 0), associate the read end of a pipe with the child process\'s standard input, and then close the corresponding end of the pipe in the \
parent process while writing data into the child process\'s standard input. In this case, code sequence is like "int pipefd[2]; pipe(pipefd); dup2(pipefd[0], 0);". Therefore, \
when I give you the Linux manual page of "dup", you should use your knowledge, and tell me that system call "dup" implicitly depend on system call "pipe". Now you know what \
are explicit and implicit dependencies, and you know the meanings of "a system call depend on another system call" and "a system call is depended upon by another system call". \
You must use your knowledge of Linux manual pages of system calls and your knowledge of the usage of all Linux system calls to generate the dependencies of system calls. \
I will give you the name of a Linux system call, and you must use your knowledge of how this system call could be used with other system calls to tell me: what system calls \
does this system call depend on and what system calls is this system call depended upon by? YOU MUST KEEP IN MIND: each system call can only appear \
at most once in the result!!! NEVER generate repeated system calls! Your answers MUST output the results in json format without any other unrelated words. '''


def QUERY_GENERATE(syscall, syscall_synopsis, simplified_description, simplified_notes):
    query = 'According to the definition of explicit and implicit dependencies of Linux system calls, generate the system calls which "%s(2)" explicitly depend and implicitly depend on, and also generate the system calls which "%s(2)" is explicitly depended and implicitly depended upon by. Generate these dependencies by the SYNOPSIS and DESCRIPTION and NOTES of "%s(2)". SYNOPSIS:"%s". DESCRIPTION:"%s". NOTES:"%s". The output dependencies MUST be Linux system calls. Output the results in json format without any other unrelated words. The format of the json file MUST be: {"explicit depend": "some system calls seperated by comma", "implicit depend": "some system calls seperated by comma", "explicit depended": "some system calls seperated by comma", "implicit depended": "some system calls seperated by comma"}. YOU MUST KEEP IN MIND: each system call can only appear at most once in the result! NEVER generate repeated system calls!'%(syscall,syscall,syscall,syscall_synopsis,simplified_description,simplified_notes)
    return query

def QUERY_FREE_GEN(syscall, gen1_result):
    query = 'This is a preliminary list of system calls which have dependencies with system call "%s". You must use your knowledge to check it and correct it according to the demand I gave you.  list:"%s". According to the definition of explicit and implicit dependencies of Linux system calls, generate the system calls which "%s" explicitly depend and implicitly depend on, and also generate the system calls which "%s" is explicitly depended and implicitly depended upon by. The output dependencies MUST be Linux system calls. Output the results in json format without any other unrelated words. The format of the json file MUST be: {"explicit depend": "some system calls seperated by comma", "implicit depend": "some system calls seperated by comma", "explicit depended": "some system calls seperated by comma", "implicit depended": "some system calls seperated by comma"}.'%(syscall, gen1_result, syscall, syscall)
    return query

def QUERY_FREE_GEN_FROM_LIST(syscall, gen1_result, condensed_synopsis, condensed_description, condensed_notes):
    query = 'This is a preliminary list of system calls which have dependencies with system call "%s". You must use your knowledge to check it and correct it according to the demand I gave you. list:"%s". You may refer to the information from the linux manual page of system call "%s": {synopsis:"%s", description:"%s", notes:"%s"}. According to the definition of explicit and implicit dependencies of Linux system calls, generate the system calls which "%s" explicitly depend and implicitly depend on, and also generate the system calls which "%s" is explicitly depended and implicitly depended upon by. The output dependencies MUST be Linux system calls. Output the results in json format without any other unrelated words. The format of the json file MUST be: {"explicit depend": "some system calls seperated by comma", "implicit depend": "some system calls seperated by comma", "explicit depended": "some system calls seperated by comma", "implicit depended": "some system calls seperated by comma"}.'%(syscall, gen1_result, syscall, condensed_synopsis, condensed_description, condensed_notes, syscall, syscall)
    return query

def QUERY_FREE_GEN_FROM_NULL(syscall, condensed_synopsis, condensed_description, condensed_notes):
    query = 'Keep to the demand I gave you, according to the definition of explicit and implicit dependencies of Linux system calls, generate the system calls which "%s" explicitly depend and implicitly depend on, and also generate the system calls which "%s" is explicitly depended and implicitly depended upon by. You may refer to the information from the linux manual page of system call "%s": {synopsis:"%s", description:"%s", notes:"%s"}. And also, you must use your knowledge of how this system call could be used with others. The output dependencies MUST be Linux system calls. Output the results in json format without any other unrelated words. The format of the json file MUST be: {"explicit depend": "some system calls seperated by comma", "implicit depend": "some system calls seperated by comma", "explicit depended": "some system calls seperated by comma", "implicit depended": "some system calls seperated by comma"}.'%(syscall, syscall, syscall, condensed_synopsis, condensed_description, condensed_notes)
    return query