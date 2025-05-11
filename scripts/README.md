# Scripts Usage


## Results Checking and Plotting

**result_parser.py**: check the found crashes in terms of Hash, Title, PoC, Existence (check the duplication in Syzbot and Google Search).
- Usage:
```python
python result_parser.py -D WORKDIR1 WORKDIR2 ... -c -u -e SYZFATAL SYZFAIL
# Pa
```



## Others

**1. diff_config.py**: diff two kernel configurations with rich printing.
- Usage: `python diff_config.py <config1_path> <config2_path>`

**2. build_llvm-project.sh**: automatically build llvm-project with specified version.
- Usage: `./build_llvm-project.sh <VERSION> (e.g., 15.0.6)`

**3. collect_repro.py**: collect reproducers from Syzbot (as syzbot limit the requests in 1 per second, we need to rewrite this script)
- Usage: `python collect_repro.py`