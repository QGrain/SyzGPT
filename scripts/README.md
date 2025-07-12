# Scripts Usage

We have some useful scripts here.

## Bug Checking

**result_parser.py**: check the found crashes in terms of Hash, Title, PoC, Existence (check the duplication in Syzbot and Google Search).

- **Synopsis**:
```bash
result_parser.py [-h] [-D CRASH_DIRS [CRASH_DIRS ...]] [-s SEARCH_HASH [SEARCH_HASH ...]] [-S SEARCH_TITLE [SEARCH_TITLE ...]] [-k KEYWORD [KEYWORD ...]] [-e EXCLUDE_KEYWORD [EXCLUDE_KEYWORD ...]]
                        [-d] [-c] [-C] [-u] [-U] [-r] [-f]

Analyze crash reports of Syzkaller.

options:
  -h, --help            show this help message and exit
  -D CRASH_DIRS [CRASH_DIRS ...], --crash_dirs CRASH_DIRS [CRASH_DIRS ...]
                        path to the directories containing crash reports
  -s SEARCH_HASH [SEARCH_HASH ...], --search_hash SEARCH_HASH [SEARCH_HASH ...]
                        [Unimpl] search the existence of bug through hash, used with -c, -C
  -S SEARCH_TITLE [SEARCH_TITLE ...], --search_title SEARCH_TITLE [SEARCH_TITLE ...]
                        search the existence of bug through title, used with -c, -C
  -k KEYWORD [KEYWORD ...], --keyword KEYWORD [KEYWORD ...]
                        keyword list that must be included in report title
  -e EXCLUDE_KEYWORD [EXCLUDE_KEYWORD ...], --exclude_keyword EXCLUDE_KEYWORD [EXCLUDE_KEYWORD ...]
                        keyword list that must be excluded in report title
  -d, --dumb            dumb mode, omit useless output
  -c, --check_exist     check existence of crashes
  -C, --check_exist_with_search
                        check existence of crashes (add google search)
  -u, --unique_only     unique crash only
  -U, --unique_only_strict
                        strict unique crash only (ignore suspicious)
  -r, --has_repro       filter out the reports that don't have any repro
  -f, --flush_cache     flush cache and re-fetch the reports
```

- **Common usage**:
```bash
python result_parser.py -D WORKDIR1 WORKDIR2 ... -C -u
```

> [!NOTE]
> For **every bug report** marked as "NO", "NO (S)" or "NO (SG)", we recommend you double check it by searching through google and syzkaller google group with "bug_func".

## Results Plotting

**bench_parser.py**: plot the curves of bench logs from different fuzzers.

- **Synopsis**:
```bash
bench_parser.py [-h] [-b [BENCH_FILE ...]] [-t TIME] [-T TITLE] [-i INTERVAL] [-k [KEYS ...]] [-r [RATIO ...]] [-l [LEGEND ...]] [-a AVERAGE] [-p] [-s] [-o OUT_DIR]

Parse fuzzing results from bench files

options:
  -h, --help            show this help message and exit
  -b [BENCH_FILE ...], --bench_file [BENCH_FILE ...]
                        bench file(s) to parse
  -t TIME, --time TIME  print the results around specified time
  -T TITLE, --title TITLE
                        title of the plot, use with -p
  -i INTERVAL, --interval INTERVAL
                        sample interval (e.g. 10m, 30m, 1h), 1h by default. BUG: please use 1h only until the bug is fixed
  -k [KEYS ...], --keys [KEYS ...]
                        keys to parse
  -r [RATIO ...], --ratio [RATIO ...]
                        calc ratio of 2 keys
  -l [LEGEND ...], --legend [LEGEND ...]
                        legends for multi bench files, work with -p
  -a AVERAGE, --average AVERAGE
                        average number, work with -p
  -p, --plot            plot, work with -b, -t, -k, -l
  -s, --stat            stat the bench log, this option is prior to the others
  -o OUT_DIR, --out_dir OUT_DIR
                        out dir to save the plot fig
```

- **Common usage**:
```bash
python bench_parser.py -b benchlogA1 benchlogA2 benchlogA3 benchlogB1 benchlogB2 benchlogB3 ... -l fuzzerA fuzzerB ... -k coverage crashes 'crash types' syscalls -t 24h -T fuzz-6.6 -a 3 -p -o ~/SyzGPT/plots/
```

## Others

**1. diff_config.py**: diff two kernel configurations with rich printing.
- Usage: `python diff_config.py <config1_path> <config2_path>`

**2. build_llvm-project.sh**: automatically build llvm-project with specified version.
- Usage: `./build_llvm-project.sh <VERSION> (e.g., 15.0.6)`

**3. collect_repro.py**: collect reproducers from Syzbot (as syzbot limit the requests in 1 per second, we need to rewrite this script)
- Usage: `python collect_repro.py`