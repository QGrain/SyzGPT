# Use SyzGPT for Directed Kernel Fuzzing

The core idea is quite intuitive: generating seeds for crash-related syscalls. 


## With PoC

For the easiest case, we have the PoCs of the crash. Then we could extract the crash syscalls as generation targets:

```bash
cd /root/SyzGPT/experiments/directed
python extract_crash_syscalls.py -i crash1.poc -o crash1_syscalls.txt
./generate_directed_corpus.sh crash1_syscalls.txt crash1_out
```

You will find the directed seed programs for target `crash1` at `./crash1_out/directed_corpus_valid/`.