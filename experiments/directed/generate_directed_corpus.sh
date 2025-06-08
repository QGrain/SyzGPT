#!/bin/bash
set -euo pipefail

# crash_syscalls=experiments/directed/crash1_syscalls.txt
crash_syscalls=${1:-}
outdir_name=${2:-}
external_corpus=${3:-/root/corpus/enriched-ci-qemu-upstream-corpus.db}
cwd=`pwd`
outdir=${cwd}/{outdir_name}
proj_dir=/root/SyzGPT
fuzzer_dir=/root/fuzzers/SyzGPT-fuzzer

if [[ -z "$crash_syscalls" || -z "${outdir_name}" ]]; then
    echo "Usage: $0 <crash-syscalls> <outdir-name> [external-corpus]" >&2
    exit 1
fi

echo "outdir: ${outdir}"

workon syzgpt

# generate round 1 seeds (3 rounds in total)
python ${proj_dir}/syzgpt_generator.py -s ${fuzzer_dir} -w ${outdir} -e ${external_corpus} -f ${crash_syscalls} -t 0 -N 3 -P 0 -F 0
# backup the round 1 raw seeds and repaired seeds
cp -r ${outdir}/generated_corpus ${outdir}/generated_corpus_round1_raw
${fuzzer_dir}/bin/syz-repair ${outdir}/generated_corpus ${outdir}/generated_corpus_round1_repair

# re-generate with 100% probability on top of round 1 seeds, which are located in ${outdir}/generated_corpus
python ${proj_dir}/syzgpt_generator.py -s ${fuzzer_dir} -w ${outdir} -e ${external_corpus} -f ${crash_syscalls} -t 0 -N 3 -P 100 -F 0
# backup the round 2 raw seeds and repaired seeds
cp -r ${outdir}/generated_corpus ${outdir}/generated_corpus_round2_raw
${fuzzer_dir}/bin/syz-repair ${outdir}/generated_corpus ${outdir}/generated_corpus_round2_repair

# re-generate with 100% probability on top of round 2 seeds, which are located in ${outdir}/generated_corpus)
python ${proj_dir}/syzgpt_generator.py -s ${fuzzer_dir} -w ${outdir} -e ${external_corpus} -f ${crash_syscalls} -t 0 -N 3 -P 100 -F 0
# backup the round 3 raw seeds and repaired seeds
cp -r ${outdir}/generated_corpus ${outdir}/generated_corpus_round3_raw
${fuzzer_dir}/bin/syz-repair ${outdir}/generated_corpus ${outdir}/generated_corpus_round3_repair
${fuzzer_dir}/bin/syz-validtor ${outdir}/generated_corpus_round3_repair ${outdir}/directed_corpus_valid
# now we get the directed corpus for ${outdir_name} at ${outdir}/directed_corpus_valid