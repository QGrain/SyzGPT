# Migration to KernelGPT


## 1 Setup and Patch KernelGPT

```bash
cd /root/fuzzers
git clone https://github.com/google/syzkaller.git SyzGPT-KernelGPT-fuzzer
cd SyzGPT-KernelGPT-fuzzer && git checkout f1b6b00
patch -p1 < /root/SyzGPT/fuzzer/SyzGPT-fuzzer_for_f1b6b00.patch
cp /root/SyzGPT/experiments/KernelGPT/sys-linux-specifications/* /root/fuzzers/SyzGPT-KernelGPT-fuzzer/sys/linux/
make -j32
```

## 2 Syscall Dependency Extration for KernelGPT

```bash
# extract builtin_syscalls.json from SyzGPT-KernelGPT-fuzzer at -o dir
python /root/SyzGPT/extractor/parse_builtin_syscalls.py -s ~/fuzzers/SyzGPT-KernelGPT-fuzzer -o ~/SyzGPT/data/KernelGPT
```

## 3 Run KernelGPT for fuzzing

Just like run vanilla Syzkaller for fuzzing:

```bash
cd /root/fuzzers/SyzGPT-KernelGPT-fuzzer
taskset -c 0-7 ./bin/syz-manager -config cfgdir/Syzkaller.cfg -bench benchdir/Syzkaller.log -statcall -backup 24h
```

## 3 Run SyzGPT-KernelGPT for fuzzing

The workflow is similar to SyzGPT for fuzzing: run SyzGPT-KernelGPT-fuzzer first.

```bash
cd /root/fuzzers/SyzGPT-KernelGPT-fuzzer
taskset -c 8-15 ./bin/syz-manager -config cfgdir/SyzGPT.cfg -bench benchdir/SyzGPT.log -statcall -backup 24h -enrich WORKDIR/generated_corpus -period 1h -repair
```

And run SyzGPT-generator. The only difference is that a flag `-K/--KGPT` should be added to `syzgpt_generator.py`

```bash
cd /root/SyzGPT && workon syzgpt
python syzgpt_generator.py -s /root/fuzzers/SyzGPT-KernelGPT-fuzzer -w /root/fuzzers/SyzGPT-KernelGPT-fuzzer/workdir/v6-1/SyzGPT/generated_corpus -D 1h -T 1h -S 24h -m 100 -P 10 -K
# -K, --KGPT: add support for KernelGPT
```