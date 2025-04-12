# Syscall Dependency Extraction

## 1 Setup

1. Install dependencies:

```bash
cd ~/SyzGPT
pip install requirements.txt
```

2. Config API_KEY in **private_config.py** (Call-level dependency extraction will use LLM)

```bash
# for security concern
cp config.py private_config.py
# and then edit API_KEY in private_config.py
```

## 2 Extract specialized call level dependency

We extract the specialized call level (syz-level) dependency through resource-based static analysis on Syzlangs.

1. Extract defined syscalls of the fuzzer:

```bash
# it will generate debug.log at ~/SyzGPT/data/debug.log and generate builtin_syscalls* at -o
cd extractor
python parse_builtin_syscalls.py -s ~/fuzzers/SyzGPT-fuzzer -o ../data/
```

2. Extract syz-level dependencies:

```bash
# it will generate syz-level dependencies at -o
python extract_syz_dependencies.py -b ../data/builtin_syscalls.json -o ../data/syz_dependencies
```

## 3 Extract system call level dependency

1. Crawler the manpage documentation by syscalls:

```bash
# it will download the docs at crawler/man_docs/SYSCALL.json
cd crawler
python get_syscall_doc.py
```

2. Extract call-level dependencies:

```bash
# -d for dumb mode, recommended
cd extractor
python extract_call_dependencies.py -f ../crawler/syscall_from_manpage.txt -d
```

## Syscall Dependency Augmentation

SyzGPT-fuzzer will automatically combine syz-level and call-level depedencies.