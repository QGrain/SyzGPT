#!/bin/bash
cd ~/demos/SyzGPT

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash1 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_1.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash1
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash1 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_1.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash1
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash1 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_1.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash1
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash2 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_2.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash2
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash2 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_2.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash2
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash2 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_2.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash2
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash3 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_3.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash3
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash3 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_3.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash3
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash3 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_3.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash3
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash4 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_4.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash4
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash4 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_4.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash4
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash4 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_4.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash4
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash5 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_5.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash5
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash5 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_5.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash5
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash5 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_5.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash5
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash6 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_6.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash6
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash6 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_6.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash6
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash6 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_6.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash6
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash7 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_7.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash7
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash7 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_7.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash7
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash7 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_7.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash7
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash8 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_8.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash8
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash8 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_8.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash8
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash8 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_8.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash8
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash9 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_9.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash9
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash9 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_9.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash9
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash9 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_9.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash9
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../

python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash10 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_10.txt -t 0 -N 3 -P 0 -F 0
cd experiments/crash10
cp -r generated_corpus generated_corpus_round1_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round1_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash10 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_10.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash10
cp -r generated_corpus generated_corpus_round2_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round2_repair
cd ../../
python syzgpt_generator.py -M Meta-Llama-3-8B-Instruct -u http://10.26.9.16:38950/v1/ -s ~/fuzzers/SyzGPT-fuzzer/ -w experiments/crash10 -e ~/corpus/enriched-ci-qemu-upstream-corpus-12-18.db -f data/crash_syscalls_10.txt -t 0 -N 3 -P 100 -F 0
cd experiments/crash10
cp -r generated_corpus generated_corpus_round3_raw
~/fuzzers/SyzGPT-fuzzer/bin/syz-repair generated_corpus generated_corpus_round3_repair
~/fuzzers/SyzGPT-fuzzer/bin/syz-validtor generated_corpus_round3_repair directed_corpus_valid
cd ../../