# SyzGPT: Unlocking Low Frequency Syscalls in Kernel Fuzzing with Dependency-Based RAG

<div align="center">
<a href="https://doi.org/10.5281/zenodo.15206336"><img alt="Artifact Zenodo" src="https://zenodo.org/badge/DOI/10.5281/zenodo.15206336.svg"/></a>
<a href="https://huggingface.co/zzra1n/CodeLlama-syz-toy"><img alt="Hugging Face" src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-CodeLlama--syz--toy-ffc107?color=ffc107&logoColor=white%22"/></a>

</div>

> [!NOTE] 
> We are still updating this project and formatting the documentations for Artifact Evaluation.

This is the implementation of paper titled "**Unlocking Low Frequency Syscalls in Kernel Fuzzing with Dependency-Based RAG**". For more details about SyzGPT, please refer to [our paper](https://zhiyu.netlify.app/files/ISSTA25_SyzGPT_Zhiyu_Camera_Ready.pdf) from ISSTA'25. We also provide a [README_for_review](./docs/README_for_review.md), which was once located in an [anonymous repository](https://anonymous.4open.science/r/SyzGPT-eval) for better understanding by reviewers.

**Quick Glance**: SyzGPT is an LLM-assisted kernel fuzzing framework for automatically generating effective seeds for low frequency syscalls (LFS). Linux kernel provides over [360 system calls](./data/builtin_syscalls.txt) and Syzkaller defines more than [4400 specialized calls](./data/builtin_variants.txt) encapsulated for specific purposes of system calls. However, many of these syscalls (called [LFS](./docs/LFS.md)) are hard to be consistently covered due to the complex dependencies and mutation uncertainty, leaving the testing space. SyzGPT can automatically extract and augment syscall dependencies for these LFS and generate effective seeds with dependency-based RAG (DRAG). Our evaluation shows that SyzGPT can improve overall code coverage and syscall coverage, and find LFS-induced vulnerabilities. We also release a toy model [🤗CodeLlama-syz-toy](https://huggingface.co/zzra1n/CodeLlama-syz-toy) specialized for Syz-program.

We also generate a [wiki page](https://deepwiki.com/QGrain/SyzGPT) for SyzGPT through [DeepWiki](https://deepwiki.com/).

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

- Hardware
  - CPU: 16+ Cores
  - Memory: 64GB+
  - Storage: 256GB+
  - GPU: None
- Software
  - OS: Ubuntu 20.04+ (20.04, 22.04 tested)
  - Compiler: GCC 11+ (11.4, 12.3 tested) or Clang 15+ (15.0.6, 16.0.6, 17.0.6 tested)
  - Python: 3.8+ (3.8-3.11 tested)
  - Syzkaller-runnable Dependencies
  - LLM API Access
- For LLM fine-tuning and serving (Optional)
  - GPU: GPU with 48GB+ (1xA800, 2xRTX 3090 tested)
  - Software: torch 2.0+ (2.0.1, 2.3.0 tested)
  - LLM Serving (fastchat tested)


### 1.2 Setup with Docker (Recommend) [⏰~10min]

We have released `qgrain/syzgpt:pretest`, which is ready for fuzzing. And we will release `qgrain/syzgpt:full` with full functionality and evaluation benchmark soon. **To understand how we build these docker images, please refer to this repo**: [QGrain/kernel-fuzz-docker-images](https://github.com/QGrain/kernel-fuzz-docker-images).

<details>
<summary>Setup with qgrain/syzgpt:pretest</summary>

To facilitate the researchers who want to test our work ASAP, we release the `qgrain/syzgpt:pretest` as an early-bird image, which includes a runnable SyzGPT-generator and SyzGPT-fuzzer (experimental configurations and code are not included).

1. Create the container

```bash
docker run -itd --name SyzGPT --privileged=true qgrain/syzgpt:pretest
# You will find SyzGPT located at /root/SyzGPT and SyzGPT-fuzzer at /root/fuzzers/SyzGPT-fuzzer
```

2. Synchronize SyzGPT repository (please always)

```bash
cd /root/SyzGPT && git pull
```

3. Minor steps

```bash
cd /root/fuzzers/SyzGPT-fuzzer && make -j32
# You need to build the fuzzer as we did not include the binaries into image to save size.

workon syzgpt
# Enter the python virtual environment with the dependencies required by SyzGPT-generator
```

</details>

<details>
<summary>Setup with qgrain/syzgpt:full</summary>

```bash
docker run -itd --name SyzGPT --privileged=true qgrain/syzgpt:full
# You will find everything is OK as expected, including the functionalities and experiments of SyzGPT.
```
</details>

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

1. Generate Seeds (**NOTE: it will interact with LLM and cost tokens**)

```bash
# cd the root of this project, e.g., /root/SyzGPT
workon syzgpt

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

2. Repair Seeds and Evaluate

```bash
# Check the Syntax Valid Rate (SVR)
/root/fuzzers/SyzGPT-fuzzer/bin/syz-validator dir WORKDIR/generated_corpus

# Repair the seeds and check SVR again
/root/fuzzers/SyzGPT-fuzzer/bin/syz-repair WORKDIR/generated_corpus WORKDIR/generated_corpus_repair

# Check the N_avg and L_avg
/root/fuzzers/SyzGPT-fuzzer/bin/syz-validator dir WORKDIR/generated_corpus_repair WORKDIR/generated_corpus_repair_valid
python /root/SyzGPT/analyzer/corpus_analyzer.py analyze -d WORKDIR/generated_corpus_repair_valid

# Check the Context Effective Rate (CER)
# It's a bit complicated, please wait for our all-in-one script
```


> [!NOTE] 
> You can run the all-in-one script to reproduce the seed generation experiments in paper Table 2.

<details>

<summary>Run seed-generation-all-in-one script</summary>

Will be released soon.

</details>

### 2.2 Run SyzGPT for fuzzing [⏰~24h]

We provide a simplest running instruction here. For detailed usage, please refer to [generator/README.md](generator/README.md) and [fuzzer/README.md](fuzzer/README.md).

1. Run SyzGPT-fuzzer:

```bash
# cd /root/fuzzers/SyzGPT-fuzzer
# e.g., WORKDIR=workdir/v6-1/SyzGPT
taskset -c 8-15 ./bin/syz-manager -config cfgdir/SyzGPT.cfg -bench benchdir/SyzGPT.log -statcall -backup 24h -enrich WORKDIR/generated_corpus -period 1h -repair
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

3. Check the results after 24h fuzzing:

```bash
# Usage of plotting script will be updated soon.
```

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
python extract_syz_dependencies.py -b ../data/builtin_syscalls.json -o ../data/dependencies/syz_level/Syzkaller_deps/
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

---

> [!NOTE] 
> The usage of the tools and scripts can be found in [scripts/README.md](scripts/README.md).


## 3 Fine-tuning LLM for Syz-programs [⏰~16h]

We have repleased a toy version of CodeLlama-syz at [Huggingface](https://huggingface.co/zzra1n/CodeLlama-syz-toy). For more details, please refer to [fine-tune/README.md](fine-tune/README.md)

## 4 Reusability

**Our approach is able to be migrated to other kernel fuzzing framework**, such as Syzkaller-like (ACTOR, ECG, KernelGPT, ...) and Healer-like (Healer and MOCK) fuzzers.

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