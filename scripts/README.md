# Scripts Usage

We have some useful scripts here.

## Bug Checking

`result_parser.py` scans syzkaller crash directories and checks possible
duplicates through the reusable `syzbot-client` package. The package supplies
typed API models, throttled transport, target discovery, indexing, and
snapshot persistence. The script can be copied by itself as long as its PyPI
dependencies are installed. Rich output is optional; only `-C` additionally
needs `ddgs`, and the script fails fast with an installation command when it
is missing.

For local development against a `syzbot-client` source checkout:

```bash
python -m pip install --editable ~/projects/syzbot-client
```

For a copied `result_parser.py`, install the published client package:

```bash
python -m pip install syzbot-client
```

Common commands:

```bash
# Check all crashes in several syzkaller workdirs against syzbot.
python scripts/result_parser.py \
  -D WORKDIR1 WORKDIR2 WORKDIR3 -c

# Also perform one cached, free ddgs/Bing-international search per unique title.
python scripts/result_parser.py \
  -D WORKDIR1 WORKDIR2 WORKDIR3 -C -u

# Check selected targets/groups or a title without scanning a workdir.
python scripts/result_parser.py -S 'possible deadlock in example_func' -c \
  --target upstream linux-6.6 linux-6.1 linux-5.15 \
  --group open fixed invalid --json
```

`target` is the user-facing CLI term for a syzbot dashboard namespace. The
default dynamically discovers and checks every namespace in syzbot's live
selector (currently Linux upstream/LTS, Android, gVisor, FreeBSD, NetBSD, and
OpenBSD). The discovered list is cached for three days and the 13-target
built-in list is used only if neither live discovery nor a cached list is
available. Use `--target ...` to request a smaller set explicitly.

The compact `Exist` column intentionally has only five values:

| Value | Meaning |
| --- | --- |
| `Yes` | An exact normalized title was found in syzbot or Web results. |
| `Maybe` | Only a same-function or other similar result was found. |
| `No` | Every requested source completed and no match was found. |
| `?` | At least one requested source failed and no positive evidence exists. |
| `--` | Existence checking was not requested. |

Use `-u` to show every result not confirmed as known (`Maybe`, `No`, and `?`),
or `-U` to show only strict `No`. Including `?` prevents a source outage from
silently hiding a crash. `-d` emits TSV. `--json` changes only the output
format: structured results go to standard output while progress and warnings
remain on standard error. It is intended for `jq`, scripts, CI jobs, archived
benchmark results, result comparison, and agent/tool ingestion. Crash scans
include hash, title, reproducer counts, existence status, workdir, timestamps,
and detailed match evidence; `-S` title checks emit title, status, and evidence.
`-f` refreshes the target list and every requested syzbot source; `-n` permits
reuse of expired target and source caches.

The parser stores stable cache files under
`${XDG_CACHE_HOME:-~/.cache}/syzkaller-result-parser/` by default:

```text
targets.json                         discovered target list (3-day TTL)
syzbot-snapshots/
  upstream/open.json                 one target/group snapshot (3-day TTL)
  upstream/fixed.json
  ...
  linux-6.6/invalid.json
web-search.json                      DDGS results (7 days; failures 10 minutes)
```

Each source shard is a complete `syzbot-client` snapshot with its own
ISO-8601 fetch time. Changing `--target` or `--group` therefore reuses every
overlapping fresh shard and fetches only missing or expired sources. A failed
refresh keeps the old shard for later runs and uses its evidence for positive
matches in the current run, while the source failure still makes unmatched
results `?` rather than `No`.

The former combined `syzbot-snapshot.json` is automatically split into source
shards when found in the selected cache directory; legacy numeric and current
ISO-8601 package timestamps are both accepted. The old parser's
`~/.cache/result_parser/` pickle/JSON files remain intentionally incompatible.
Caches created by intermediate development versions under
`~/.cache/syzgpt-result-parser/` or `~/.cache/result-parser/` remain valid:
move the whole directory to the new default once, or temporarily select it
with `--cache-dir`.

`No` means “not found in the successfully checked sources,” not proof that a
crash is a new vulnerability. Similar-function matches are review candidates,
not automatic duplicate decisions.

`-C` fixes ddgs to its free Bing backend with region `us-en`. This avoids the
much longer cumulative timeout of ddgs's multi-engine `auto` mode and does not
require an API key, account, payment, proxy, or local service.

The repository pins `ddgs==9.5.5`: it is the last tested release that exposes
the selected `bing` backend without requiring `httpx>=0.28.1` and
`fake-useragent>=2.2.0`. `primp==0.15.0` is pinned with it because newer primp
releases removed several impersonation profiles referenced by DDGS 9.5.5 and
otherwise print a harmless fallback warning.

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
