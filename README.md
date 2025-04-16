# SyzGPT: Unlocking Low Frequency Syscalls in Kernel Fuzzing with Dependency-Based RAG

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15206336.svg)](https://doi.org/10.5281/zenodo.15206336)

> We are still updating this project and formatting the documentations for Artifact Evaluation.

This is the implementation of paper titled "**Unlocking Low Frequency Syscalls in Kernel Fuzzing with Dependency-Based RAG**". For more details about SyzGPT, please refer to [our paper]() from ISSTA'25. We also provide a [README_for_review](./docs/README_for_review.md), which was once located in an [anonymous repository](https://anonymous.4open.science/r/SyzGPT-eval) for better understanding by reviewers.

**Quick Glance**: SyzGPT is an LLM-assisted kernel fuzzing framework for automatically generating effective seeds for low frequency syscalls (LFS). Linux kernel provides over [360 system calls](./data/builtin_syscalls.txt) and Syzkaller defines more than [4400 specialized calls](./data/builtin_variants.txt) encapsulated for specific purposes of system calls. However, many of these syscalls (called [LFS](./docs/LFS.md)) are hard to be consistently covered due to the complex dependencies and mutation uncertainty, leaving the testing space. SyzGPT can automatically extract and augment syscall dependencies for these LFS and generate effective seeds with dependency-based RAG (DRAG). Our evaluation shows that SyzGPT can improve overall code coverage and syscall coverage, and find LFS-induced vulnerabilities. We also release a toy model [🤗CodeLlama-syz-toy](https://huggingface.co/zzra1n/CodeLlama-syz-toy) specialized for Syz-program.

**Project Structure**

```bash
  ____                 ____  ____  _____                       
 / ___|  _   _  ____  / ___||  _ \|_   _|
 \___ \ | | | ||_  / | |  _|| |_) | | |
  ___) || |_| | / /_ | |_| ||  __/  | | 
 |____/  \__, //____| \____||_|     |_|  
         |___/                                                     
.
├── analyzer/           # Corpus Analyzer
├── crawler/            # Crawler for Linux Manpages
├── data/               # Data used in SyzGPT
├── examples/           # Examples for better understanding
├── experiments/        # Experiments
├── extractor/          # Two-Level Syscall Dependency Extractor
├── fine-tune/          # Fine-tuning LLM specialized for Syz-programs
├── fuzzer/             # SyzGPT-fuzzer
├── generator/          # SyzGPT-generator
├── scripts/            # Some useful scripts
...
├── config.py           # Configs, need to be copied as private_config.py
└── syzgpt_generator.py # Main entry of SyzGPT-generator
```

## 1 Setup

### 1.1 Environment Requirements

- For running SyzGPT:
  - Machine with 16+ CPU cores, 64GB+ memory (For parallel fuzzing experiments)
  - Ubuntu 20.04 + (20.04 and 22.04 tested)
  - Syzkaller-runnable dependencies (setup according to Syzkaller project or use our docker)
  - Python 3.8+ (Python-3.8, 3.9, 3.10, 3.11 tested)
  - LLM API access or self-deployed LLM
- For kernel compilation:
  - Clang 15+ (15.0.6, 16.0.6, 17.0.6 tested)
  - GCC 11+ (11.4 and 12.2 tested)
- For LLM fine-tuning or serving:
  - GPU with 48GB+ (1 x A800, 2 x RTX 3090 tested)
  - torch 2.0+


### 1.2 Setup with Docker (Recommend) [⏰~10min]

We will release our docker image on dockerhub soon.

```bash
docker run -itd --name SyzGPT --privileged=true DOCKER_IMAGE
# You will find SyzGPT located at /root/SyzGPT
# And SyzGPT-fuzzer is located at /root/fuzzers/SyzGPT-fuzzer
```

### 1.3 Setup from scratch [⏰~15min]

You can also setup SyzGPT from scratch on a Ubuntu 20.04/22.04. Or base on our image [`qgrain/kernel-fuzz:v1`](https://hub.docker.com/repository/docker/qgrain/kernel-fuzz/general).

```bash
docker run -itd --name SyzGPT-from-scratch --privileged=true qgrain/kernel-fuzz:v1
```

1. Clone this project:

```bash
# Recommend at /root/SyzGPT, so that the following instructions can match with the path.
# If you are a normal user on a physical machine, feel free to clone it at a convenient place.
git clone https://github.com/QGrain/SyzGPT.git
```

2. Setup **SyzGPT-generator**: Please refer to Setup section in [generator/README.md](generator/README.md)

3. Setup **SyzGPT-fuzzer**: Please refer to [fuzzer/README.md](fuzzer/README.md)


## 2 Usage

SyzGPT can serve as a standalone seed generator through SyzGPT-generator (**Section 2.1**). It can also cooperate with SyzGPT-fuzzer for kernel fuzzing (**Section 2.2**).

We have open-souced the augmented syscall depencies at [data/dependencies](data/dependencies/). So you can directly run SyzGPT without extracting syscall dependency. You can also extract the syscall dependencies on your own (**Section 2.3**).

For any questions in using SyzGPT, you may refer to [Troubleshooting](./docs/Troubleshooting.md) or feel free to raise an issue.

### 2.1 Run SyzGPT for seed generation [⏰~30min]

We provide a simplest running instruction here. For detailed usage, please refer to [generator/README.md](generator/README.md).

Suppose you have: 
- A corpus generated by at local Syzkaller or some other existing fuzzers. We provide a `corpus_24h.db` at [data/corpus_24h.db](./data/corpus_24h.db) for reproduction.
- A file containing target syscalls. We provide a `sampled_variants.txt` at [data/sampled_variants.txt](./data/sampled_variants.txt) for reproduction.

(**NOTE: it will interact with LLM and cost tokens**)

```bash
# cd the root of this project, e.g., /root/SyzGPT

# (1) Use official OpenAI api (it will load api_key, llm_model, ... from private_config.py)
python syzgpt_generator.py -s /root/fuzzers/SyzGPT-fuzzer -w WORKDIR -e data/corpus_24h.db -f sampled_variants.txt

# (2) Use third party api
python syzgpt_generator.py -M gpt-3.5-turbo-16k -u https://api.expansion.chat/v1/ -k API_KEY -s /root/fuzzers/SyzGPT-fuzzer -w WORKDIR -e data/corpus_24h.db -f sampled_variants.txt

# (3) Use local LLMs
python syzgpt_generator.py -M CodeLlama-syz-toy -u http://IP:PORT/v1/ -s /root/fuzzers/SyzGPT-fuzzer -w WORKDIR -e data/corpus_24h.db -f sampled_variants.txt
```

Explanation of Parameters:
- `-s`: path to the SyzGPT-fuzzer, must be specified.
- `-w`: output the generated results and logs to `WORKDIR`, must be specified.
- `-e`: path to external corpus, only nessary in one-time seed generation.
- `-f`: path to the file containing target syscall list, only needed in one-time seed generation.
- `-c`: you can also specify the target syscalls through `-c CALL1 CALL2 ...` manually, instead of `-f`.
- `-M`: model name, used with third party api or local LLM.
- `-u`: base_url to api address or local hosted LLM.
- `-k`: api_key for third party api service.

You will find the outputs in `WORKDIR` look like:

```bash
├── external_corpus/          # external corpus specified through -e
├── generated_corpus/         # generated seeds in Syz-program format
├── generation_history.json   # generation history for feedback-guided seed generation
├── query_prompts/            # generation logs including query prompts and results, can be used for fine-tuning.
├── reverse_index.json        # reverse index for DRAG
└── target_syscalls/          # generation targets
```

### 2.2 Run SyzGPT for fuzzing [⏰~24h]

We provide a simplest running instruction here. For detailed usage, please refer to [generator/README.md](generator/README.md) and [fuzzer/README.md](fuzzer/README.md).

1. Run SyzGPT-fuzzer:

```bash
# cd the location where you setup SyzGPT-fuzzer
taskset -c 8-15 ./bin/syz-manager -config /root/SyzGPT/fuzzer/cfgdir/SyzGPT.cfg -bench benchdir/SyzGPT.log -statcall -backup 24h -enrich WORKDIR/generated_corpus -period 1h -repair
```

Explanation of Parameters (refer to [fuzzer/README.md](fuzzer/README.md) for more details):
- `-statcall`: enable syscall tracking during fuzzing.
- `-backup`: backup **rawcover**, **corpus.db**, **CoveredCalls**, and **crahes** every 24h.
- `-enrich`: load the enriched seeds from `WORKDIR/generated_corpus` every `INTERNAL` (1h).
- `-period`: `INTERVAL` of loading enriched seeds.
- `-repair`: enable program repair which is implemented in SyzGPT-fuzzer.

2. Run SyzGPT-generator (**NOTE: it will interact with LLM and cost tokens**):

```bash
# cd the root of this project
python syzgpt_generator.py -s /root/fuzzers/SyzGPT-fuzzer -w /root/fuzzers/SyzGPT-fuzzer/workdir/v6-1/SyzGPT/generated_corpus -D 1h -T 1h -S 24h -m 100 -P 10
# seemingly, you can also use other api service
# or local hosted LLM with -M, -u, -k (introduced in section 2.1)
```

Explanation of Parameters (refer to [generator/README.md](generator/README.md) for more details):
- `-s` and `-w` have been introduced above.
- `-D`: an empirical delay (1h) before generator start to work, which leave the fuzzer to explore by default.
- `-T`: generate seeds every `INTERVAL` (1h), need to be in the same pace with `-enrich` in fuzzer.
- `-S`: stop generating after 24h.
- `-m`: max generation amount, 100 here.
- `-P`: probability of feedback-guided re-generation for failed seeds, 10% here.

### 2.3 Extract syscall dependency

**Extract specialized call level dependency [⏰~3min]**:

We extract the specialized call level (syz-level) dependency through resource-based static analysis on Syzlangs.

1. Extract defined syscalls of the fuzzer (different fuzzers would have different builtin syscalls, e.g., KernelGPT):

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

**Extract system call level dependency [⏰~1h]**:

1. Crawler the manpage documentation by syscalls:

```bash
# it will download the docs at crawler/man_docs/SYSCALL.json
cd crawler
python get_syscall_doc.py
```

2. Extract call-level dependencies (**NOTE: it will interact with LLM and cost tokens**):

```bash
# -d for dumb mode, recommended
cd extractor
python extract_call_dependencies.py -f ../crawler/syscall_from_manpage.txt -d
```

### 2.4 Introduce some intersting tools developed with SyzGPT

There are other useful tools under `scripts/`.

**1. diff_config.py**: diff two kernel configurations with rich printing.
- Usage: `python diff_config.py <config1_path> <config2_path>`

**2. result_parser.py**: visualize the fuzzing crashes with de-duplication.
- Usage: `python result_parser.py -D WORKDIR1 WORKDIR2 ... -c -u -e SYZFATAL SYZFAIL`

**3. build_llvm-project.sh**: automatically build llvm-project with specified version.
- Usage: `./build_llvm-project.sh <VERSION> (e.g., 15.0.6)`

**4. collect_repro.py**: collect reproducers from Syzbot (as syzbot limit the requests in 1 per second, we need to rewrite this script)
- Usage: `python collect_repro.py`

## 3 Fine-tuning LLM for Syz-programs [⏰~16h]

We have repleased a toy version of CodeLlama-syz at [Huggingface](https://huggingface.co/zzra1n/CodeLlama-syz-toy). For more details, please refer to [fine-tune/README.md](fine-tune/README.md)

## 4 Reusability

Our approach is able to be migrated to other kernel fuzzing framework, such as Syzkaller-like (ACTOR, ECG, KernelGPT, ...) and Healer-like (Healer and MOCK) fuzzers.

### 4.1 Migrate to Syzkaller-like fuzzers[⏰~10min]

We have demonstrated the migration on KernelGPT, please refer to the implementation instruction in [experiments/KernelGPT/README.md](experiments/KernelGPT/README.md).

### 4.2 Migrate to Healer-like fuzzers

Simple as migrating to Syzkaller-like, as long as you are familiar with RUST.

We also prepare a instruction for migrating to MOCK, please refer to the implementation instruction in [experiments/MOCK/README.md](experiments/MOCK/README.md).

## 5 Credit

Thanks to Zhiyu Zhang ([@QGrain](https://github.com/QGrain)) and Longxing Li ([@x0v0l](https://github.com/x0v0l)) for their valuable contributions to this project.

## 6 Citation

In case you would like to cite SyzGPT, you may use the following BibTex entry:

```bash
# TBD
```