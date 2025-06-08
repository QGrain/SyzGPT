# Motivation of SyzGPT

> To be completed. Well, it seems not so important.  XD

## Observations

> To be completed.

```bash
cd /root/SyzGPT/experiments/observation/
python plot_lfsc_distribution.py
```

## Capability Tests

Based on these observation , we have done several capability tests to figure out the potentials of LLMs in assisting kernel fuzzing.

### Test 1

Ask LLM about the SYNOPSIS of linux syscalls.

```bash
cd /root/SyzGPT/crawler/ && python get_syscall_doc.py
cd /root/SyzGPT/experiments/capability
python capability_test.py --test 1
python compare_synopsis.py
```

$$S_{h} = \sum\nolimits_{i=0}^{N_1}\max\nolimits_{j=0}^{N_2}(f^{'}(h_1[i], h_2[j]))$$

$$S_{d} = f^{'}(r_1, r_2) + \sum_{i=0}^{N_{arg}}(f^{'}(a_1[i], a_2[i])+f^{'}(t_1[i], t_2[i]))$$

$$S_{max} = N_2 \times w_h + (1 + 2N_{args}) \times w_d$$

$$C_k = \frac{S_{h}\times w_h + S_{d}\times w_d}{S_{max}} \times 100$$

where $C_k$ is the correctness (from 0 to 100) of generation for the $k$-th syscall, $S_h$ and $w_h$ are the correct score and weight of headers in generated synopsis, $S_d$ and $w_d$ are the correct score and weight of declarations in generated synopsis, $S_{max}$ is the maximum score of the generation, $f^{'}$ is the function to calculate the similarity of two strings, $h1$ and $h2$ are the headers of LLM generation and manual page (1 for LLM and 2 for manpage), $r_i$, $a_i$ and $t_i$ ($i$ is 1 or 2) represent the return type, argument name and argument type of wrapper function declarations. We perform the documentation knowledge presence test for 522 syscalls available on the Linux manual page. Results show that 384 of manual page syscalls are valid in the format of synopsis, 84 have no wrapper function, 20 are unimplemented, 5 have no synopsis, and 29 are other invalid types. And LLM successfully generated information with valid synopsis for 507 syscalls, In the failures, 3 are unimplemented and 12 have no synopsis.

### Test 2

Ask LLM to generate C programs for specified kernel functions.

```bash
cd /root/SyzGPT/experiments/capability
python capability_test.py --test 2
```

### Test 3

Ask LLM to generate Syz-programs for specified linux syscalls.

```bash
cd /root/SyzGPT/experiments/capability
python capability_test.py --test 3 --variant_mode
```

