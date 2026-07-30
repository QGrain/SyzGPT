"""Analyze syzkaller crash directories with the reusable syzbot-client package.

The script contains the crash scanner, CLI, Web search, and presentation
logic. ``syzbot-client`` supplies typed public-API models, target discovery,
throttled transport, title indexing, and snapshot persistence. ``-c`` checks
syzbot, while ``-C`` also performs one cached ddgs query per unmatched unique
title. Rich is optional; without it, the script emits a tab-separated table.
"""

# Future TODOs:
# - Optionally derive normalized top-stack signatures to strengthen or weaken
#   same-function "Maybe" matches without promoting them directly to "Yes".
# - Optionally aggregate recurring crashes across trials/workdirs while
#   preserving every raw crash and its provenance in machine-readable output.

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from syzbot_client import (
        DEFAULT_TARGETS,
        BugGroup,
        BugSummary,
        CacheError,
        Snapshot,
        SourceFailure,
        SyzbotClient,
        SyzbotError,
        SyzbotIndex,
        extract_function,
        load_snapshot,
        normalize_title,
        save_snapshot,
    )
except ImportError as exc:
    raise SystemExit(
        "result_parser.py requires syzbot-client; install it with: "
        "python -m pip install syzbot-client"
    ) from exc

VERSION = "2.2.0"
TARGET_CACHE_SCHEMA_VERSION = 1
WEB_CACHE_SCHEMA_VERSION = 1
KNOWN_TARGETS = tuple(target.id for target in DEFAULT_TARGETS)
DEFAULT_GROUPS = ("open", "fixed", "invalid")
GROUPS = frozenset(DEFAULT_GROUPS)
DEFAULT_EXCLUDES = (
    "SYZFATAL",
    "SYZFAIL",
    "no output from test machine",
    "suppressed report",
)
DEFAULT_CACHE_TTL = 3 * 86400
TARGET_CACHE_TTL = 3 * 86400
WEB_CACHE_TTL = 7 * 86400
WEB_FAILURE_TTL = 600
DDGS_BACKEND = "bing"
TARGET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def log(message: str) -> None:
    print(message, file=sys.stderr)


def verbose(message: str, enabled: bool) -> None:
    if enabled:
        log(message)


def default_cache_dir() -> Path:
    """Return an XDG-compatible cache directory independent of the host repo."""

    configured = os.environ.get("XDG_CACHE_HOME")
    if configured:
        xdg_cache_home = Path(configured).expanduser()
        if xdg_cache_home.is_absolute():
            return xdg_cache_home / "syzkaller-result-parser"
    return Path.home() / ".cache" / "syzkaller-result-parser"


def atomic_json_dump(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def load_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        log(f"[!] Ignoring unreadable cache {path}: {exc}")
        return None
    if not isinstance(data, dict):
        log(f"[!] Ignoring cache that is not a JSON object: {path}")
        return None
    return data


class Existence(str, Enum):
    YES = "Yes"
    MAYBE = "Maybe"
    NO = "No"
    UNKNOWN = "?"
    NOT_CHECKED = "--"


@dataclass(frozen=True, slots=True)
class Evidence:
    source: str
    kind: str
    title: str
    url: str = ""
    target: str = ""
    group: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in (
                ("source", self.source),
                ("kind", self.kind),
                ("title", self.title),
                ("url", self.url),
                ("target", self.target),
                ("group", self.group),
            )
            if value
        }


@dataclass(frozen=True, slots=True)
class CheckResult:
    status: Existence
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True, slots=True)
class SnapshotOptions:
    targets: tuple[str, ...]
    groups: tuple[str, ...]
    cache_dir: Path
    cache_ttl: float
    flush: bool
    no_ttl: bool
    verbose: bool

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(
            f"{target}/{group}" for target in self.targets for group in self.groups
        )

    @property
    def legacy_cache_path(self) -> Path:
        """Combined snapshot path used by the pre-sharding implementation."""

        return self.cache_dir / "syzbot-snapshot.json"

    def source_cache_path(self, target: str, group: str) -> Path:
        """Return the stable cache path for one target/group source."""

        if not TARGET_ID.fullmatch(target) or group not in GROUPS:
            raise ValueError(f"invalid syzbot source: {target}/{group}")
        return self.cache_dir / "syzbot-snapshots" / target / f"{group}.json"


def load_client_targets(client: SyzbotClient) -> tuple[str, ...]:
    """Discover all public namespaces through syzbot-client."""

    return tuple(target.id for target in client.fetch_targets())


def _targets_from_cache(data: Mapping[str, Any]) -> tuple[str, ...]:
    if data.get("schema-version") != TARGET_CACHE_SCHEMA_VERSION:
        raise ValueError("unsupported target cache schema")
    raw_targets = data.get("targets")
    if not isinstance(raw_targets, list):
        raise TypeError("target cache has no targets list")
    targets = tuple(
        dict.fromkeys(
            item.strip()
            for item in raw_targets
            if isinstance(item, str)
            and item.strip()
            and TARGET_ID.fullmatch(item.strip())
        )
    )
    if not targets:
        raise ValueError("target cache is empty")
    return targets


def load_discovered_targets(
    cache_path: Path,
    *,
    cache_ttl: float,
    flush: bool,
    no_ttl: bool,
    enabled_verbose: bool,
    loader: Callable[[], tuple[str, ...]],
) -> tuple[str, ...]:
    """Load the live target list with cached and built-in fallbacks."""

    cached_targets: tuple[str, ...] | None = None
    cached_at = 0.0
    cached = load_json_object(cache_path)
    if cached is not None:
        try:
            cached_targets = _targets_from_cache(cached)
            cached_at = float(cached.get("fetched-at", 0))
            if not flush and (no_ttl or time.time() - cached_at <= cache_ttl):
                verbose(
                    f"[+] Using target cache from {cache_path}",
                    enabled_verbose,
                )
                return cached_targets
        except (TypeError, ValueError) as exc:
            log(f"[!] Ignoring incompatible target cache: {exc}")
            cached_targets = None

    try:
        targets = tuple(dict.fromkeys(loader()))
        if not targets or any(not TARGET_ID.fullmatch(target) for target in targets):
            raise ValueError("target discovery returned invalid data")
    except Exception as exc:  # noqa: BLE001
        if cached_targets:
            log(
                "[!] Could not refresh syzbot targets; using the stale "
                f"cached list: {exc}"
            )
            return cached_targets
        log(
            "[!] Could not discover syzbot targets; using the built-in "
            f"{len(KNOWN_TARGETS)}-target fallback: {exc}"
        )
        return KNOWN_TARGETS

    try:
        atomic_json_dump(
            cache_path,
            {
                "schema-version": TARGET_CACHE_SCHEMA_VERSION,
                "fetched-at": time.time(),
                "targets": list(targets),
            },
        )
    except OSError as exc:
        log(f"[!] Could not save target cache: {exc}")
    return targets


def _load_snapshot_compat(path: Path) -> Snapshot | None:
    """Load package snapshots and upgrade numeric development timestamps."""

    try:
        return load_snapshot(path)
    except CacheError as package_error:
        raw = load_json_object(path)
        if raw is None:
            return None
        fetched_at = raw.get("fetched-at")
        if isinstance(fetched_at, bool) or not isinstance(fetched_at, (int, float)):
            log(f"[!] Ignoring incompatible syzbot cache {path}: {package_error}")
            return None
        upgraded = dict(raw)
        upgraded["fetched-at"] = (
            datetime.fromtimestamp(float(fetched_at), timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        try:
            snapshot = Snapshot.from_dict(upgraded)
            if snapshot.schema_version != 1 or snapshot.api_version != 1:
                raise ValueError("unsupported snapshot or public API version")
            return snapshot
        except (TypeError, ValueError) as exc:
            log(f"[!] Ignoring incompatible syzbot cache {path}: {exc}")
            return None
    except SyzbotError as exc:
        log(f"[!] Ignoring incompatible syzbot cache {path}: {exc}")
        return None


def _read_source_snapshot(path: Path, source: str) -> Snapshot | None:
    snapshot = _load_snapshot_compat(path)
    if snapshot is None:
        return None
    try:
        if snapshot.sources != (source,) or snapshot.failures:
            raise ValueError("source shard must be complete and contain one source")
        target, group = source.rsplit("/", 1)
        if any(
            bug.target != target or bug.group.value != group for bug in snapshot.bugs
        ):
            raise ValueError("source shard contains bugs from another source")
        return snapshot
    except ValueError as exc:
        log(f"[!] Ignoring incompatible syzbot cache {path}: {exc}")
        return None


def _import_combined_snapshot(options: SnapshotOptions) -> None:
    """Seed missing source shards from the former combined snapshot."""

    try:
        legacy_stat = options.legacy_cache_path.stat()
    except FileNotFoundError:
        return
    except OSError as exc:
        log(f"[!] Could not inspect combined syzbot cache: {exc}")
        return
    marker_path = options.cache_dir / "syzbot-snapshots" / ".combined-import.json"
    fingerprint = {
        "schema-version": 1,
        "legacy-size": legacy_stat.st_size,
        "legacy-mtime-ns": legacy_stat.st_mtime_ns,
    }
    if load_json_object(marker_path) == fingerprint:
        return

    combined = _load_snapshot_compat(options.legacy_cache_path)
    if combined is None:
        return
    failed_sources = {
        f"{failure.target}/{failure.group.value}" for failure in combined.failures
    }

    imported = 0
    import_failed = False
    for source in combined.sources:
        if source in failed_sources:
            continue
        try:
            target, group = source.rsplit("/", 1)
            destination = options.source_cache_path(target, group)
        except ValueError:
            continue
        if destination.exists():
            continue
        shard = Snapshot(
            bugs=tuple(
                bug
                for bug in combined.bugs
                if bug.target == target and bug.group.value == group
            ),
            fetched_at=combined.fetched_at,
            failures=(),
            sources=(source,),
        )
        try:
            save_snapshot(shard, destination)
            imported += 1
        except CacheError as exc:
            import_failed = True
            log(f"[!] Could not import source cache {destination}: {exc}")
    if not import_failed:
        try:
            atomic_json_dump(marker_path, fingerprint)
        except OSError as exc:
            log(f"[!] Could not save combined-cache import marker: {exc}")
    if imported:
        verbose(
            f"[+] Imported {imported} source shards from "
            f"{options.legacy_cache_path}",
            options.verbose,
        )


def load_client_snapshot(
    options: SnapshotOptions,
    client: SyzbotClient,
) -> Snapshot:
    """Reuse and refresh independent target/group cache shards."""

    _import_combined_snapshot(options)
    bugs: list[BugSummary] = []
    failures: list[SourceFailure] = []
    fetched_times: list[datetime] = []
    for target in options.targets:
        for group in options.groups:
            source = f"{target}/{group}"
            cache_path = options.source_cache_path(target, group)
            cached = _read_source_snapshot(cache_path, source)
            fresh = cached is not None and (
                options.no_ttl
                or (datetime.now(timezone.utc) - cached.fetched_at).total_seconds()
                <= options.cache_ttl
            )
            if not options.flush and fresh:
                bugs.extend(cached.bugs)
                fetched_times.append(cached.fetched_at)
                verbose(f"[+] Source cache hit: {source}", options.verbose)
                continue
            try:
                fetched = client.fetch_group(target, BugGroup(group))
                fetched_at = datetime.now(timezone.utc)
                shard = Snapshot(
                    bugs=fetched,
                    fetched_at=fetched_at,
                    failures=(),
                    sources=(source,),
                )
                bugs.extend(fetched)
                fetched_times.append(fetched_at)
                verbose(
                    f"[+] {source}: {len(fetched)} bugs",
                    options.verbose,
                )
                try:
                    save_snapshot(shard, cache_path)
                except CacheError as exc:
                    log(f"[!] Could not save source cache {cache_path}: {exc}")
            except SyzbotError as exc:
                failure = SourceFailure(target, BugGroup(group), str(exc))
                failures.append(failure)
                log(f"[!] {source}: {exc}")
                if cached is not None:
                    bugs.extend(cached.bugs)
                    fetched_times.append(cached.fetched_at)
                    verbose(
                        f"[+] Using stale {source} cache for positive matches",
                        options.verbose,
                    )
    return Snapshot(
        bugs=tuple(bugs),
        fetched_at=min(fetched_times, default=datetime.now(timezone.utc)),
        failures=tuple(failures),
        sources=options.sources,
    )


class TitleIndex:
    """Adapt syzbot-client matches to this CLI's compact evidence model."""

    def __init__(self, bugs: Iterable[BugSummary]) -> None:
        self.index = SyzbotIndex(bugs)

    def match(self, title: str, limit: int = 3) -> tuple[Evidence, ...]:
        return tuple(
            Evidence(
                source="syzbot",
                kind=match.kind.value,
                title=match.bug.title,
                url=match.bug.link,
                target=match.bug.target,
                group=match.bug.group.value,
            )
            for match in self.index.match(title, max_similar=limit)[:limit]
        )


@dataclass(frozen=True, slots=True)
class WebOutcome:
    complete: bool
    evidence: tuple[Evidence, ...] = ()
    error: str = ""


class DdgsSearcher:
    """One automatic, cached ddgs search per normalized title."""

    def __init__(self, cache_path: Path, *, enabled_verbose: bool = False) -> None:
        self.cache_path = cache_path
        self.verbose = enabled_verbose
        raw = load_json_object(cache_path) or {}
        if raw.get("schema-version") == WEB_CACHE_SCHEMA_VERSION and isinstance(
            raw.get("entries"), dict
        ):
            self.entries: dict[str, Any] = dict(raw["entries"])
        else:
            self.entries = {}
        self.dirty = False
        self._ddgs: Any = None
        self._import_error = ""
        self.checked: set[str] = set()
        self.failures: dict[str, str] = {}

    def _client(self) -> Any:
        if self._ddgs is not None:
            return self._ddgs
        if self._import_error:
            raise RuntimeError(self._import_error)
        try:
            from ddgs import DDGS
        except ImportError as exc:
            self._import_error = (
                "ddgs is not installed in this Python environment; run: "
                "python -m pip install ddgs==9.5.5 primp==0.15.0"
            )
            raise RuntimeError(self._import_error) from exc
        self._ddgs = DDGS(timeout=10)
        return self._ddgs

    def ensure_available(self) -> None:
        """Fail fast for a missing optional dependency before network work."""

        self._client()
        stale_keys = [
            key
            for key, entry in self.entries.items()
            if isinstance(entry, Mapping)
            and "ddgs is not installed" in str(entry.get("error", ""))
        ]
        for key in stale_keys:
            self.entries.pop(key, None)
        if stale_keys:
            self.dirty = True

    def _record(self, key: str, outcome: WebOutcome) -> WebOutcome:
        self.checked.add(key)
        if outcome.complete:
            self.failures.pop(key, None)
        else:
            self.failures[key] = outcome.error or "unknown Web search error"
        return outcome

    @staticmethod
    def _evidence_from_results(
        title: str, results: Iterable[Mapping[str, Any]]
    ) -> tuple[Evidence, ...]:
        normalized = normalize_title(title)
        function = extract_function(title)
        similar: list[Evidence] = []
        for item in results:
            result_title = str(item.get("title", "")).strip()
            body = str(item.get("body", "")).strip()
            url = str(item.get("href", item.get("url", ""))).strip()
            searchable = " ".join(f"{result_title} {body}".casefold().split())
            if normalized and normalized in searchable:
                return (
                    Evidence(
                        source="web",
                        kind="exact",
                        title=result_title or body[:160],
                        url=url,
                    ),
                )
            if function and re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(function)}(?![A-Za-z0-9_])",
                searchable,
            ):
                similar.append(
                    Evidence(
                        source="web",
                        kind="similar",
                        title=result_title or body[:160],
                        url=url,
                    )
                )
                if len(similar) >= 3:
                    break
        return tuple(similar)

    @staticmethod
    def _entry_to_outcome(entry: Mapping[str, Any]) -> WebOutcome:
        evidence = tuple(
            Evidence(
                source="web",
                kind=str(item.get("kind", "")),
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
            )
            for item in entry.get("evidence", ())
            if isinstance(item, Mapping)
        )
        return WebOutcome(
            complete=bool(entry.get("complete", False)),
            evidence=evidence,
            error=str(entry.get("error", "")),
        )

    def search(self, title: str) -> WebOutcome:
        key = normalize_title(title)
        now = time.time()
        cached = self.entries.get(key)
        if isinstance(cached, Mapping):
            try:
                age = now - float(cached.get("checked-at", 0))
                ttl = WEB_CACHE_TTL if cached.get("complete") else WEB_FAILURE_TTL
                if age <= ttl:
                    outcome = self._entry_to_outcome(cached)
                    verbose(f"[+] Web cache hit: {title}", self.verbose)
                    return self._record(key, outcome)
            except (TypeError, ValueError):
                verbose(
                    f"[!] Ignoring invalid Web cache entry: {title}",
                    self.verbose,
                )
                self.entries.pop(key, None)
                self.dirty = True
        try:
            raw_results = self._client().text(
                title,
                region="us-en",
                safesearch="off",
                max_results=10,
                backend=DDGS_BACKEND,
            )
            results = [item for item in raw_results if isinstance(item, Mapping)]
            if not results:
                raise RuntimeError(
                    "ddgs returned no results; the search may have been blocked"
                )
            evidence = self._evidence_from_results(title, results)
            outcome = WebOutcome(True, evidence)
        # ddgs can surface backend-specific exception classes that are not
        # part of a stable public hierarchy. All mean "source unavailable".
        except Exception as exc:  # noqa: BLE001
            outcome = WebOutcome(
                False,
                error=f"{type(exc).__name__}: {exc}",
            )
        self.entries[key] = {
            "checked-at": now,
            "complete": outcome.complete,
            "error": outcome.error,
            "evidence": [item.to_dict() for item in outcome.evidence],
        }
        self.dirty = True
        return self._record(key, outcome)

    def log_summary(self) -> None:
        if not self.failures:
            return
        example = next(iter(self.failures.values()))
        log(
            f"[!] Web search failed for {len(self.failures)}/"
            f"{len(self.checked)} unique unmatched titles; those without "
            f"syzbot evidence are marked '?'. Example: {example}"
        )

    def save(self) -> None:
        if not self.dirty:
            return
        atomic_json_dump(
            self.cache_path,
            {
                "schema-version": WEB_CACHE_SCHEMA_VERSION,
                "entries": self.entries,
            },
        )
        self.dirty = False


def check_title(
    title: str,
    index: TitleIndex,
    syzbot_complete: bool,
    web: DdgsSearcher | None,
) -> CheckResult:
    syzbot_evidence = index.match(title)
    if any(item.kind == "exact" for item in syzbot_evidence):
        return CheckResult(Existence.YES, syzbot_evidence)

    web_outcome: WebOutcome | None = None
    if web is not None:
        web_outcome = web.search(title)
        if any(item.kind == "exact" for item in web_outcome.evidence):
            return CheckResult(
                Existence.YES,
                syzbot_evidence + web_outcome.evidence,
            )

    evidence = syzbot_evidence
    if web_outcome is not None:
        evidence += web_outcome.evidence
    if evidence:
        return CheckResult(Existence.MAYBE, evidence)

    web_complete = web_outcome is None or web_outcome.complete
    if syzbot_complete and web_complete:
        return CheckResult(Existence.NO)
    return CheckResult(Existence.UNKNOWN)


@dataclass(slots=True)
class CrashRecord:
    hash: str
    title: str
    workdir: str
    discover: float
    update: float | None
    syz_repro: int
    c_repro: int
    result: CheckResult = field(
        default_factory=lambda: CheckResult(Existence.NOT_CHECKED)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash,
            "title": self.title,
            "syz_repro": self.syz_repro,
            "c_repro": self.c_repro,
            "exist": self.result.status.value,
            "workdir": self.workdir,
            "discover": datetime.fromtimestamp(self.discover, timezone.utc).isoformat(),
            "update": (
                datetime.fromtimestamp(self.update, timezone.utc).isoformat()
                if self.update is not None
                else None
            ),
            "evidence": [item.to_dict() for item in self.result.evidence],
        }


def find_workdirs(paths: Sequence[str]) -> list[Path]:
    workdirs: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        if path.name == "crashes" and path.is_dir():
            workdirs.add(path.parent)
            continue
        if (path / "crashes").is_dir():
            workdirs.add(path)
            continue
        if not path.is_dir():
            continue
        for root, dirs, _files in os.walk(path):
            if "crashes" in dirs:
                workdirs.add(Path(root).resolve())
                dirs.remove("crashes")
    return sorted(workdirs)


def workdir_label(path: Path) -> str:
    if path.parent.name:
        return f"{path.parent.name}/{path.name}"
    return path.name


def count_reproducers(crash_path: Path) -> tuple[int, int]:
    syz = sum((crash_path / name).is_file() for name in ("repro.prog", "repro.txt"))
    c = sum((crash_path / name).is_file() for name in ("repro.cprog", "repro.c"))
    return int(syz), int(c)


def scan_crashes(
    workdirs: Iterable[Path],
    *,
    excludes: Sequence[str],
    hash_filters: Sequence[str],
) -> tuple[list[CrashRecord], int]:
    records: list[CrashRecord] = []
    total = 0
    for workdir in workdirs:
        crash_root = workdir / "crashes"
        try:
            crash_paths = sorted(crash_root.iterdir())
        except OSError as exc:
            log(f"[!] Skipping {crash_root}: cannot list directory: {exc}")
            continue
        for crash_path in crash_paths:
            if not crash_path.is_dir():
                continue
            total += 1
            crash_hash = crash_path.name
            if hash_filters and not any(
                crash_hash.startswith(value) for value in hash_filters
            ):
                continue
            description = crash_path / "description"
            try:
                title = description.read_text(
                    encoding="utf-8", errors="replace"
                ).strip()
            except OSError as exc:
                log(f"[!] Skipping {crash_path}: cannot read description: {exc}")
                continue
            if not title or any(value in title for value in excludes):
                continue
            try:
                files = [item for item in crash_path.iterdir() if item.is_file()]
            except OSError as exc:
                log(f"[!] Could not list all files in {crash_path}: {exc}")
                files = [description]
            mtimes: list[float] = []
            update_times: list[float] = []
            for item in files:
                try:
                    mtime = item.stat().st_mtime
                except OSError:
                    continue
                mtimes.append(mtime)
                if item.name != "description":
                    update_times.append(mtime)
            if not mtimes:
                try:
                    mtimes.append(crash_path.stat().st_mtime)
                except OSError:
                    mtimes.append(time.time())
            syz_repro, c_repro = count_reproducers(crash_path)
            records.append(
                CrashRecord(
                    hash=crash_hash,
                    title=title,
                    workdir=workdir_label(workdir),
                    discover=min(mtimes),
                    update=max(update_times) if update_times else None,
                    syz_repro=syz_repro,
                    c_repro=c_repro,
                )
            )
    return records, total


def status_markup(status: Existence) -> str:
    styles = {
        Existence.YES: "[b green]Yes[/]",
        Existence.MAYBE: "[b yellow]Maybe[/]",
        Existence.NO: "[b red]No[/]",
        Existence.UNKNOWN: "[b magenta]?[/]",
        Existence.NOT_CHECKED: "--",
    }
    return styles[status]


def timestamp(value: float | None) -> str:
    if value is None:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(value))


def filtered_records(
    records: Iterable[CrashRecord], args: argparse.Namespace
) -> list[CrashRecord]:
    selected: list[CrashRecord] = []
    keywords = args.keyword or ()
    for record in sorted(records, key=lambda item: item.discover, reverse=True):
        if args.has_repro and record.syz_repro + record.c_repro == 0:
            continue
        if args.unique_only_strict and record.result.status is not Existence.NO:
            continue
        if args.unique_only and record.result.status not in (
            Existence.MAYBE,
            Existence.NO,
            Existence.UNKNOWN,
        ):
            continue
        if keywords and not any(keyword in record.title for keyword in keywords):
            continue
        selected.append(record)
    return selected


def print_plain(records: Sequence[CrashRecord]) -> None:
    print("Hash\tTitle\tSyz\tC\tExist\tWorkdir\tDiscover\tUpdate")
    for record in records:
        print(
            "\t".join(
                (
                    record.hash[:7],
                    record.title.replace("\t", " "),
                    str(record.syz_repro),
                    str(record.c_repro),
                    record.result.status.value,
                    record.workdir,
                    timestamp(record.discover),
                    timestamp(record.update),
                )
            )
        )


def print_rich(records: Sequence[CrashRecord], caption: str) -> bool:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        return False
    table = Table(
        title="[b]Crash Results[/]",
        caption=caption,
        caption_style="b i white",
        show_edge=True,
        show_lines=True,
    )
    for column in (
        "Hash",
        "Title",
        "Syz",
        "C",
        "Exist",
        "Workdir",
        "Discover(sorted)",
        "Update",
    ):
        table.add_column(column, justify="left")
    for record in records:
        update = timestamp(record.update)
        if record.update is not None and record.update - record.discover > 86400:
            update = f"[cyan]{update}[/]"
        table.add_row(
            f"[b]{record.hash[:7]}[/]",
            record.title,
            str(record.syz_repro),
            str(record.c_repro),
            status_markup(record.result.status),
            record.workdir,
            timestamp(record.discover),
            update,
        )
    Console().print(table)
    return True


def print_title_results(results: Mapping[str, CheckResult], use_json: bool) -> None:
    if use_json:
        print(
            json.dumps(
                [
                    {
                        "title": title,
                        "exist": result.status.value,
                        "evidence": [item.to_dict() for item in result.evidence],
                    }
                    for title, result in results.items()
                ],
                indent=2,
            )
        )
        return
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        print("Title\tExist")
        for title, result in results.items():
            print(f"{title}\t{result.status.value}")
        return
    table = Table(title="[b]Search Results[/]", show_edge=True, show_lines=True)
    table.add_column("Title")
    table.add_column("Exist")
    for title, result in results.items():
        table.add_row(title, status_markup(result.status))
    Console().print(table)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze syzkaller crash reports.",
        epilog=(
            "Known targets: "
            + ", ".join(KNOWN_TARGETS)
            + ". Other valid namespace slugs are accepted."
        ),
    )
    parser.add_argument(
        "-D",
        "--crash_dirs",
        nargs="+",
        help="workdirs, crashes directories, or parent directories to scan",
    )
    parser.add_argument(
        "-s",
        "--search_hash",
        nargs="+",
        default=(),
        help="only include crash hashes with one of these prefixes",
    )
    parser.add_argument(
        "-S",
        "--search_title",
        nargs="+",
        help="check one or more titles without scanning crash directories",
    )
    parser.add_argument("-k", "--keyword", nargs="+")
    parser.add_argument("-e", "--exclude_keyword", nargs="+")
    parser.add_argument(
        "-d",
        "--dumb",
        action="store_true",
        help="emit a compact tab-separated table",
    )
    parser.add_argument(
        "-c",
        "--check_exist",
        action="store_true",
        help="check selected syzbot targets",
    )
    parser.add_argument(
        "-C",
        "--check_exist_with_search",
        action="store_true",
        help="check syzbot and automatically search the Web with ddgs",
    )
    parser.add_argument(
        "-u",
        "--unique_only",
        action="store_true",
        help="show Maybe, No, and incomplete (?) results only",
    )
    parser.add_argument(
        "-U",
        "--unique_only_strict",
        action="store_true",
        help="show strict No results only",
    )
    parser.add_argument(
        "-r",
        "--has_repro",
        action="store_true",
        help="show crashes that have a syz or C reproducer",
    )
    parser.add_argument(
        "-f",
        "--flush_cache",
        action="store_true",
        help="refresh the syzbot target list and bug snapshot",
    )
    parser.add_argument(
        "-n",
        "--no_cache_ttl",
        action="store_true",
        help="use existing syzbot target/snapshot caches regardless of age",
    )
    parser.add_argument(
        "--target",
        nargs="+",
        default=None,
        metavar="TARGET",
        help=(
            "syzbot targets to check; by default (or with 'all'), discover "
            "and use every public target"
        ),
    )
    parser.add_argument(
        "--group",
        nargs="+",
        choices=DEFAULT_GROUPS,
        default=list(DEFAULT_GROUPS),
        help="bug groups to check (default: open fixed invalid)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=default_cache_dir(),
        help=(
            "cache directory (default: "
            "$XDG_CACHE_HOME/syzkaller-result-parser or "
            "~/.cache/syzkaller-result-parser)"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show cache, source, and match details",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.crash_dirs and not args.search_title:
        parser.error("one of --crash-dirs or --search-title is required")
    if args.search_title and not (args.check_exist or args.check_exist_with_search):
        parser.error("--search-title requires -c or -C")
    if args.search_hash and not args.crash_dirs:
        parser.error("--search-hash requires --crash-dirs")
    if args.target is not None:
        if "all" in args.target and args.target != ["all"]:
            parser.error("'all' cannot be combined with explicit targets")
        invalid = [
            target
            for target in args.target
            if target != "all" and not TARGET_ID.fullmatch(target)
        ]
        if invalid:
            parser.error(f"invalid target name: {invalid[0]!r}")
        args.target = list(dict.fromkeys(args.target))
    args.group = list(dict.fromkeys(args.group))


def run(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[[], SyzbotClient] = SyzbotClient,
    snapshot_loader: Callable[[SnapshotOptions, SyzbotClient], Snapshot] = (
        load_client_snapshot
    ),
    target_loader: Callable[[SyzbotClient], tuple[str, ...]] = load_client_targets,
) -> int:
    start = time.time()
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)

    check = args.check_exist or args.check_exist_with_search
    web = (
        DdgsSearcher(
            args.cache_dir / "web-search.json",
            enabled_verbose=args.verbose,
        )
        if args.check_exist_with_search
        else None
    )
    if web is not None:
        try:
            web.ensure_available()
        except RuntimeError as exc:
            parser.error(str(exc))

    snapshot = Snapshot((), datetime.now(timezone.utc))
    index = TitleIndex(())
    client: SyzbotClient | None = None
    if check:
        client = client_factory()
        automatic_targets = args.target is None or args.target == ["all"]
        targets = (
            load_discovered_targets(
                args.cache_dir / "targets.json",
                cache_ttl=TARGET_CACHE_TTL,
                flush=args.flush_cache,
                no_ttl=args.no_cache_ttl,
                enabled_verbose=args.verbose,
                loader=lambda: target_loader(client),
            )
            if automatic_targets
            else tuple(args.target)
        )
        log(f"[+] Targets ({len(targets)}): {', '.join(targets)}")
        log("[+] Loading syzbot bug snapshot")
        snapshot = snapshot_loader(
            SnapshotOptions(
                targets=targets,
                groups=tuple(args.group),
                cache_dir=args.cache_dir,
                cache_ttl=DEFAULT_CACHE_TTL,
                flush=args.flush_cache,
                no_ttl=args.no_cache_ttl,
                verbose=args.verbose,
            ),
            client,
        )
        index = TitleIndex(snapshot.bugs)
        log(
            f"[+] Indexed {len(snapshot.bugs)} syzbot bugs "
            f"from {len(snapshot.sources) - len(snapshot.failures)}/"
            f"{len(snapshot.sources)} target/group sources "
            f"({len(targets)} targets x {len(args.group)} groups)"
        )

    memo: dict[str, CheckResult] = {}

    def lookup(title: str) -> CheckResult:
        key = normalize_title(title)
        if key not in memo:
            memo[key] = check_title(title, index, snapshot.complete, web)
            if args.verbose:
                result = memo[key]
                verbose(
                    f"[+] {result.status.value}: {title}",
                    True,
                )
                for item in result.evidence:
                    verbose(
                        f"    {item.source}/{item.kind}: {item.title} {item.url}",
                        True,
                    )
        return memo[key]

    try:
        if args.search_title:
            results = {title: lookup(title) for title in args.search_title}
            print_title_results(results, args.json)
            return 0

        try:
            workdirs = find_workdirs(args.crash_dirs)
        except FileNotFoundError as exc:
            parser.error(f"path does not exist: {exc}")
        if not workdirs:
            parser.error("no workdir containing a crashes directory was found")
        log(f"[+] Scanning {len(workdirs)} workdirs")
        excludes = list(DEFAULT_EXCLUDES)
        for value in args.exclude_keyword or ():
            if value not in excludes:
                excludes.append(value)
        records, total = scan_crashes(
            workdirs,
            excludes=excludes,
            hash_filters=args.search_hash,
        )
        if check:
            for record in records:
                record.result = lookup(record.title)
            counts = Counter(record.result.status.value for record in records)
            log(
                "[+] Existence status: "
                + ", ".join(
                    f"{status.value}={counts[status.value]}"
                    for status in (
                        Existence.YES,
                        Existence.MAYBE,
                        Existence.NO,
                        Existence.UNKNOWN,
                    )
                )
            )

        selected = filtered_records(records, args)
        if args.json:
            print(
                json.dumps(
                    [record.to_dict() for record in selected],
                    indent=2,
                )
            )
        elif args.dumb or not print_rich(
            selected,
            ("Exist: Yes=known, Maybe=similar, No=not found, ?=incomplete"),
        ):
            print_plain(selected)
        has_repro = sum(record.syz_repro + record.c_repro > 0 for record in records)
        log(
            f"[+] Done in {time.time() - start:.2f}s: "
            f"{len(records)}/{total} valid crashes, {has_repro} have repro, "
            f"{len(selected)} printed"
        )
        return 0
    finally:
        if client is not None:
            client.close()
        if web is not None:
            web.log_summary()
            try:
                web.save()
            except OSError as exc:
                log(f"[!] Could not save Web cache: {exc}")


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
