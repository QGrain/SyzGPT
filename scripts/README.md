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

## Results Analysis and Plotting

**bench_parser.py**: analyze and plot syzkaller-like bench logs. Logs are
ordered by fuzzer and then by repeat.

- `stat`: print observed metrics at one or more target uptimes.
- `plot`: generate metric-over-time and optional VIR-over-coverage figures,
  together with CSV and JSON provenance. Incomplete curves remain
  observed-only unless `--curve-completion` is explicitly selected.

- **Common usage**:
```bash
# Statistics only
python bench_parser.py stat -b benchlogA{1..3} benchlogB{1..3} -a 3 \
  -l fuzzerA fuzzerB -t 6h 12h 24h \
  -k coverage crashes 'crash types' 'exec total'

# Publication-style plots (no figure title by default)
python bench_parser.py plot -b benchlogA{1..3} benchlogB{1..3} -a 3 \
  -l fuzzerA fuzzerB -t 24h -i 1h \
  -k coverage crashes 'crash types' 'exec total' \
  --error-band sd -o ../plots/
```

Use `--curve-completion repeat` for a horizontal tail, or
`--curve-completion trend` for a growth-rate continuation. The `auto` mode
selects between them per fuzzer and metric. Add `-D` to display inferred tails
as dashed lines for inspection. See `python bench_parser.py stat --help`,
`plot --help`, and `plot --help-all` for the complete options.

## Others

**1. diff_config.py**: diff two kernel configurations with rich printing.
- Usage: `python diff_config.py <config1_path> <config2_path>`

**2. build_llvm-project.sh**: automatically build llvm-project with specified version.
- Usage: `./build_llvm-project.sh <VERSION> (e.g., 15.0.6)`

**3. collect_repro.py**: collect reproducers from Syzbot (as syzbot limit the requests in 1 per second, we need to rewrite this script)
- Usage: `python collect_repro.py`
