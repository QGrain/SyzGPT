# SyzGPT-fuzzer

**Since the compilation of Syzkaller requires `.git` directory, we need to patch SyzGPT-fuzzer based on a specific commit of Syzkaller.**

Due to a significant refactoring on March 12, 2024, Syzkaller underwent some changes in its behavior patterns (e.g., fuzzer no longer exists in the qemu vm). Therefore, we provide patches for SyzGPT-fuzzer for both pre-refactoring ([f1b6b00](https://github.com/google/syzkaller/commit/f1b6b00)) and post-refactoring (TBD) Syzkaller.

## 1 Setup


1. Clone syzkaller to somewhere:

```bash
# e.g., suppose you are in a docker container, clone syzkaller to /root/fuzzers/SyzGPT-fuzzer
cd /root/fuzzers
git clone https://github.com/google/syzkaller.git SyzGPT-fuzzer
```

2. Checkout to a selected commit of `pre-refactoring` or `post-refactoring`:

```bash
cd SyzGPT-fuzzer
git checkout f1b6b00 # or TBD commit
```

3. Apply our patch:

```bash
# suppose this project is located at /root/SyzGPT
patch -p1 < /root/SyzGPT/fuzzer/SyzGPT-fuzzer_for_f1b6b00.patch
# patch -p1 < /root/SyzGPT/fuzzer/SyzGPT-fuzzer_for_TBD.patch
```

4. Compile SyzGPT-fuzzer:

```bash
make -j32
```

5. Prepare the directories for fuzzing:

```bash
mkdir benchdir workdir
```

## 2 Usage


We have introduced the following useful options in SyzGPT-fuzzer:

- `-statcall`: Trace the growth of covered syscalls during fuzzing. Used with `-bench /path/to/BENCHLOG`. Notice: the measurement would be biased when the fuzzer instance is initialized with an existing corpus.db. In this case, you need to remove the bias by: (1) unpacking the corpus.db at a specific time (e.g., corpus.db_1_24h). (2) analyzing the unpacked corpus dir with `analyzer/corpus_analyzer.db analyze -d /path/to/unpacked_corpus_1_24h` (3) calculating the bias number of syscalls by subtracting "number of variants" from the length of "CoveredCalls_1_24h". (4) subtracting the bias from every "syscalls" number in bench log chunk. Don't worry, we will address this issue later and remove these prompts as they will no longer be needed.
- `-backup INTERVAL`: Backup the current **rawcover**, **CoveredCalls**, **corpus.db**, and **crashes** every `INTERVAL`, which can be specified by time str like "2h", "24h", "2d2h2m2s", and so on. Notice: since the size of crashes dir may be very large after a long period of fuzzing, we set a maximum backup time threshold "7d" only for crashes by default.
- `-enrich CORPUS_DIR`: Enrich the fuzzing by periodically load seeds from `CORPUS_DIR`, where the `syzgpt_generator` would also constantly generate seeds to. Used with `-period INTERVAL`, better used with `-repair`.
- `-period INTERVAL`: Load the enriched seeds from `CORPUS_DIR` every `INTERVAL`.
- `-repair`: Repair the enriched seeds with our heuristic rules before loading.
- `-dump`: Dump every executed program and its coverage during fuzzing at `WORKDIR/dump/`.

And we provide two example fuzzing configs at [Syzkaller.cfg](./Syzkaller.cfg) and [SyzGPT.cfg](./SyzGPT.cfg).

Recommend to run fuzzing inside a screen or tmux:

```bash
# recommended
screen -S v6-1-syzkaller
# or
tmux new -s v6-1-SyzGPT-fuzzer
```

**Run SyzGPT-fuzzer as vanilla Syzkaller**:

```bash
# you can specify the CPUs if you like
cd /root/fuzzers/SyzGPT-fuzzer
taskset -c 0-7 ./bin/syz-manager -config cfgdir/Syzkaller.cfg -bench benchdir/Syzkaller.log -statcall -backup 24h
```

**Run SyzGPT-fuzzer with enriched seeds**:

```bash
# suppose the WORKDIR in SyzGPT.cfg is /root/fuzzers/SyzGPT-fuzzer/workdir/v6-1/SyzGPT
taskset -c 8-15 ./bin/syz-manager -config cfgdir/SyzGPT.cfg -bench benchdir/SyzGPT.log -statcall -backup 24h -enrich WORKDIR/generated_corpus -period 1h -repair
```

## 3 Check Results

- Plot the growth of **coverage**, **syscalls**, **new\ inputs**...

```bash
python /root/SyzGPT/scripts/bench_parser.py -b BENCH1.log BENCH2.log ... -k coverage syscalls new\ inputs -l Syzkaller SyzGPT-fuzzer ... -t 24h -p -o ./
```

- Visualize the crashes

```bash
python /root/SyzGPT/scripts/result_parser.py -D /path/to/WORKDIR1/crashes /path/to/WORKDIR2/crashes ... -c
```