from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import result_parser as parser


def test_default_cache_dir_is_xdg_compatible_and_repo_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/custom-cache")

    assert parser.default_cache_dir() == Path(
        "/tmp/custom-cache/syzkaller-result-parser"
    )
    assert "syzgpt" not in (SCRIPTS / "result_parser.py").read_text().lower()


def test_default_cache_dir_ignores_relative_xdg_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/cache")

    assert (
        parser.default_cache_dir() == Path.home() / ".cache" / "syzkaller-result-parser"
    )


def test_target_discovery_uses_stale_cache_when_refresh_fails(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "targets.json"
    parser.atomic_json_dump(
        cache,
        {
            "schema-version": parser.TARGET_CACHE_SCHEMA_VERSION,
            "fetched-at": 1,
            "targets": ["upstream", "linux-6.6"],
        },
    )

    def fail() -> tuple[str, ...]:
        raise parser.SyzbotError("offline")

    targets = parser.load_discovered_targets(
        cache,
        cache_ttl=0,
        flush=True,
        no_ttl=False,
        enabled_verbose=False,
        loader=fail,
    )

    assert targets == ("upstream", "linux-6.6")


def test_title_index_distinguishes_exact_and_same_function() -> None:
    index = parser.TitleIndex(
        (
            parser.BugSummary(
                "upstream",
                parser.BugGroup.OPEN,
                "KASAN: use-after-free in foo.isra.3 (2)",
                "/bug?extid=exact",
            ),
            parser.BugSummary(
                "linux-6.1",
                parser.BugGroup.FIXED,
                "WARNING in bar",
                "/bug?extid=similar",
            ),
        )
    )

    exact = index.match("  kasan: USE-AFTER-FREE in foo.isra.3 ")
    similar = index.match("possible deadlock in bar.constprop.0")

    assert [item.kind for item in exact] == ["exact"]
    assert exact[0].target == "upstream"
    assert [item.kind for item in similar] == ["similar"]
    assert parser.extract_function("BUG at bar.cold") == "bar"


def test_check_title_is_conservative_for_partial_sources() -> None:
    empty = parser.TitleIndex(())
    assert (
        parser.check_title("BUG in missing", empty, True, None).status
        is parser.Existence.NO
    )
    assert (
        parser.check_title("BUG in missing", empty, False, None).status
        is parser.Existence.UNKNOWN
    )

    class FailedWeb:
        def search(self, _title: str) -> parser.WebOutcome:
            return parser.WebOutcome(False, error="rate limited")

    assert (
        parser.check_title("BUG in missing", empty, True, FailedWeb()).status
        is parser.Existence.UNKNOWN
    )


def test_unique_filter_keeps_unknown_results_visible() -> None:
    records = []
    for index, status in enumerate(
        (
            parser.Existence.YES,
            parser.Existence.MAYBE,
            parser.Existence.NO,
            parser.Existence.UNKNOWN,
        )
    ):
        records.append(
            parser.CrashRecord(
                hash=str(index),
                title=f"result {status.value}",
                workdir="test/workdir",
                discover=float(index),
                update=None,
                syz_repro=0,
                c_repro=0,
                result=parser.CheckResult(status),
            )
        )
    args = SimpleNamespace(
        has_repro=False,
        unique_only_strict=False,
        unique_only=True,
        keyword=(),
    )

    selected = parser.filtered_records(records, args)

    assert {record.result.status for record in selected} == {
        parser.Existence.MAYBE,
        parser.Existence.NO,
        parser.Existence.UNKNOWN,
    }


def test_workdir_discovery_prunes_and_deduplicates_overlapping_inputs(
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "cnos" / "1-basic"
    crash = workdir / "crashes" / "0123456789abcdef"
    crash.mkdir(parents=True)
    (crash / "description").write_text("WARNING in example\n", encoding="utf-8")

    found = parser.find_workdirs(
        [str(tmp_path), str(workdir), str(workdir / "crashes")]
    )

    assert found == [workdir.resolve()]


def test_scan_crashes_handles_reproducers_and_missing_update(
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "cnos" / "2-kasan"
    first = workdir / "crashes" / ("a" * 40)
    second = workdir / "crashes" / ("b" * 40)
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "description").write_text("WARNING in first\n", encoding="utf-8")
    (first / "repro.prog").write_text("syz_emit_ethernet()\n", encoding="utf-8")
    (first / "repro.c").write_text("int main(void) {}\n", encoding="utf-8")
    (second / "description").write_text("WARNING in second\n", encoding="utf-8")

    records, total = parser.scan_crashes(
        [workdir],
        excludes=parser.DEFAULT_EXCLUDES,
        hash_filters=(),
    )
    by_title = {record.title: record for record in records}

    assert total == 2
    assert (
        by_title["WARNING in first"].syz_repro,
        by_title["WARNING in first"].c_repro,
    ) == (1, 1)
    assert by_title["WARNING in first"].update is not None
    assert by_title["WARNING in second"].update is None


def test_ddgs_search_is_cached_once_per_normalized_title(tmp_path: Path) -> None:
    class FakeDdgs:
        def __init__(self) -> None:
            self.queries: list[str] = []
            self.kwargs: list[dict[str, object]] = []

        def text(self, query: str, **kwargs: object) -> list[dict[str, str]]:
            self.queries.append(query)
            self.kwargs.append(kwargs)
            return [
                {
                    "title": "syzbot: KASAN: use-after-free in foo",
                    "body": "A matching report",
                    "href": "https://example.test/result",
                }
            ]

    cache = tmp_path / "web.json"
    searcher = parser.DdgsSearcher(cache)
    fake = FakeDdgs()
    searcher._ddgs = fake

    first = searcher.search("KASAN: use-after-free in foo")
    second = searcher.search("KASAN: use-after-free in foo (3)")
    searcher.save()

    assert first.complete and first.evidence[0].kind == "exact"
    assert second == first
    assert fake.queries == ["KASAN: use-after-free in foo"]
    assert fake.kwargs[0]["backend"] == "bing"
    assert fake.kwargs[0]["region"] == "us-en"
    assert json.loads(cache.read_text(encoding="utf-8"))["schema-version"] == 1


def test_empty_ddgs_response_is_not_treated_as_not_found(tmp_path: Path) -> None:
    class EmptyDdgs:
        def text(self, _query: str, **_kwargs: object) -> list[object]:
            return []

    searcher = parser.DdgsSearcher(tmp_path / "web.json")
    searcher._ddgs = EmptyDdgs()

    outcome = searcher.search("unavailable search in example")

    assert not outcome.complete
    assert "no results" in outcome.error


def test_ddgs_preflight_discards_cached_missing_dependency_errors(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "web.json"
    parser.atomic_json_dump(
        cache,
        {
            "schema-version": parser.WEB_CACHE_SCHEMA_VERSION,
            "entries": {
                "warning in example": {
                    "checked-at": 1,
                    "complete": False,
                    "error": "RuntimeError: ddgs is not installed",
                    "evidence": [],
                }
            },
        },
    )
    searcher = parser.DdgsSearcher(cache)
    searcher._ddgs = object()

    searcher.ensure_available()

    assert searcher.entries == {}
    assert searcher.dirty


def test_invalid_web_cache_entry_is_replaced(tmp_path: Path) -> None:
    cache = tmp_path / "web.json"
    parser.atomic_json_dump(
        cache,
        {
            "schema-version": parser.WEB_CACHE_SCHEMA_VERSION,
            "entries": {
                "warning in example": {
                    "checked-at": "not-a-time",
                    "complete": True,
                    "evidence": None,
                }
            },
        },
    )

    class FakeDdgs:
        def text(self, _query: str, **_kwargs: object) -> list[dict[str, str]]:
            return [
                {
                    "title": "An unrelated result",
                    "body": "No matching function",
                    "href": "https://example.test/unrelated",
                }
            ]

    searcher = parser.DdgsSearcher(cache)
    searcher._ddgs = FakeDdgs()
    outcome = searcher.search("WARNING in example")

    assert outcome.complete
    assert outcome.evidence == ()
    assert isinstance(searcher.entries["warning in example"]["checked-at"], float)


def test_failed_refresh_uses_but_does_not_overwrite_stale_source_cache(
    tmp_path: Path,
) -> None:
    options = parser.SnapshotOptions(
        targets=("upstream",),
        groups=("open",),
        cache_dir=tmp_path,
        cache_ttl=0,
        flush=True,
        no_ttl=False,
        verbose=False,
    )
    cache = options.source_cache_path("upstream", "open")
    complete = parser.Snapshot(
        bugs=(
            parser.BugSummary(
                "upstream",
                parser.BugGroup.OPEN,
                "WARNING in known",
                "/bug?extid=known",
            ),
        ),
        fetched_at=datetime.fromtimestamp(1, timezone.utc),
        failures=(),
        sources=("upstream/open",),
    )
    parser.save_snapshot(complete, cache)

    class FailingClient:
        def fetch_group(
            self, _target: str, _group: parser.BugGroup
        ) -> tuple[parser.BugSummary, ...]:
            raise parser.SyzbotError("offline")

    refreshed = parser.load_client_snapshot(options, FailingClient())

    assert not refreshed.complete
    assert refreshed.bugs == complete.bugs
    assert parser.load_snapshot(cache) == complete


def test_source_cache_reuses_overlap_when_target_and_group_sets_change(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str]] = []

    class FakeClient:
        def fetch_group(
            self, target: str, group: parser.BugGroup
        ) -> tuple[parser.BugSummary, ...]:
            calls.append((target, group.value))
            return (
                parser.BugSummary(
                    target,
                    group,
                    f"WARNING in {target}_{group.value}",
                    f"/bug?extid={target}-{group.value}",
                ),
            )

    def options(
        targets: tuple[str, ...], groups: tuple[str, ...]
    ) -> parser.SnapshotOptions:
        return parser.SnapshotOptions(
            targets=targets,
            groups=groups,
            cache_dir=tmp_path,
            cache_ttl=parser.DEFAULT_CACHE_TTL,
            flush=False,
            no_ttl=False,
            verbose=False,
        )

    client = FakeClient()
    first = parser.load_client_snapshot(options(("upstream",), ("open",)), client)
    second = parser.load_client_snapshot(
        options(("upstream",), ("open", "fixed")), client
    )
    third = parser.load_client_snapshot(
        options(("upstream", "linux-6.6"), ("open", "fixed")), client
    )

    assert calls == [
        ("upstream", "open"),
        ("upstream", "fixed"),
        ("linux-6.6", "open"),
        ("linux-6.6", "fixed"),
    ]
    assert len(first.bugs) == 1
    assert len(second.bugs) == 2
    assert len(third.bugs) == 4


def test_combined_snapshot_is_imported_into_source_shards(
    tmp_path: Path,
) -> None:
    options = parser.SnapshotOptions(
        targets=("upstream", "linux-6.6"),
        groups=("open",),
        cache_dir=tmp_path,
        cache_ttl=parser.DEFAULT_CACHE_TTL,
        flush=False,
        no_ttl=False,
        verbose=False,
    )
    combined = parser.Snapshot(
        bugs=(
            parser.BugSummary(
                "upstream",
                parser.BugGroup.OPEN,
                "WARNING in cached",
                "/bug?extid=cached",
            ),
        ),
        fetched_at=datetime.now(timezone.utc),
        failures=(),
        sources=("upstream/open", "linux-6.6/open"),
    )
    parser.save_snapshot(combined, options.legacy_cache_path)

    class UnusedClient:
        def fetch_group(self, *_args: object) -> tuple[object, ...]:
            raise AssertionError("fresh imported shards must avoid network requests")

    loaded = parser.load_client_snapshot(options, UnusedClient())

    assert loaded.complete
    assert loaded.bugs == combined.bugs
    assert options.source_cache_path("upstream", "open").exists()
    assert options.source_cache_path("linux-6.6", "open").exists()
    assert (tmp_path / "syzbot-snapshots" / ".combined-import.json").exists()


def test_snapshot_cache_reads_legacy_numeric_timestamp(tmp_path: Path) -> None:
    snapshot = parser.Snapshot(
        bugs=(
            parser.BugSummary(
                "linux-6.6",
                parser.BugGroup.OPEN,
                "INFO: task hung in example",
                "/bug?extid=example",
            ),
        ),
        fetched_at=datetime.fromtimestamp(1, timezone.utc),
        failures=(
            parser.SourceFailure(
                "freebsd",
                parser.BugGroup.FIXED,
                "HTTP 503",
            ),
        ),
        sources=("linux-6.6/open", "freebsd/fixed"),
    )
    encoded = snapshot.to_dict()
    encoded["fetched-at"] = 1
    cache = tmp_path / "legacy.json"
    parser.atomic_json_dump(cache, encoded)

    assert parser._load_snapshot_compat(cache) == snapshot


def test_cli_json_uses_injected_snapshot_loader(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workdir = tmp_path / "workdir"
    crash = workdir / "crashes" / "0123456789abcdef"
    crash.mkdir(parents=True)
    title = "possible deadlock in input_inject_event"
    (crash / "description").write_text(f"{title}\n", encoding="utf-8")

    def load(
        options: parser.SnapshotOptions, _client: parser.SyzbotClient
    ) -> parser.Snapshot:
        assert options.sources == (
            "upstream/open",
            "upstream/fixed",
            "upstream/invalid",
        )
        return parser.Snapshot(
            bugs=(
                parser.BugSummary(
                    "upstream",
                    parser.BugGroup.OPEN,
                    title,
                    "/bug?extid=known",
                ),
            ),
            fetched_at=datetime.now(timezone.utc),
            failures=(),
            sources=options.sources,
        )

    class FakeClient:
        def close(self) -> None:
            pass

    exit_code = parser.run(
        [
            "-D",
            str(workdir),
            "-c",
            "--target",
            "upstream",
            "--json",
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
        client_factory=FakeClient,
        snapshot_loader=load,
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output[0]["exist"] == "Yes"
    assert output[0]["evidence"][0]["group"] == "open"


def test_cli_discovers_all_targets_when_target_is_omitted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workdir = tmp_path / "workdir"
    crash = workdir / "crashes" / "0123456789abcdef"
    crash.mkdir(parents=True)
    (crash / "description").write_text("WARNING in future_target\n", encoding="utf-8")
    target_calls = 0

    def load_targets(_client: parser.SyzbotClient) -> tuple[str, ...]:
        nonlocal target_calls
        target_calls += 1
        return ("upstream", "linux-6.6")

    def load_snapshot(
        options: parser.SnapshotOptions,
        _client: parser.SyzbotClient,
    ) -> parser.Snapshot:
        assert options.targets == ("upstream", "linux-6.6")
        assert len(options.sources) == 6
        return parser.Snapshot(
            bugs=(),
            fetched_at=datetime.now(timezone.utc),
            failures=(),
            sources=options.sources,
        )

    class FakeClient:
        def close(self) -> None:
            pass

    exit_code = parser.run(
        [
            "-D",
            str(workdir),
            "-c",
            "--json",
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
        client_factory=FakeClient,
        snapshot_loader=load_snapshot,
        target_loader=load_targets,
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert target_calls == 1
    assert output[0]["exist"] == "No"


def test_parser_discovers_targets_through_client() -> None:
    class FakeClient:
        def fetch_targets(self) -> tuple[SimpleNamespace, ...]:
            return (
                SimpleNamespace(id="upstream"),
                SimpleNamespace(id="linux-6.6"),
            )

    assert parser.load_client_targets(FakeClient()) == (
        "upstream",
        "linux-6.6",
    )


def test_parser_cli_is_self_contained(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workdir = tmp_path / "workdir"
    crash = workdir / "crashes" / "0123456789abcdef"
    crash.mkdir(parents=True)
    title = "WARNING in parser_example"
    (crash / "description").write_text(f"{title}\n", encoding="utf-8")

    class FakeClient:
        def __init__(self) -> None:
            self.closed = False
            self.groups: list[str] = []

        def fetch_targets(self) -> tuple[SimpleNamespace, ...]:
            return (SimpleNamespace(id="upstream"),)

        def fetch_group(
            self, target: str, group: parser.BugGroup
        ) -> tuple[parser.BugSummary, ...]:
            self.groups.append(group.value)
            if group is not parser.BugGroup.OPEN:
                return ()
            return (
                parser.BugSummary(
                    target,
                    group,
                    title,
                    "/bug?extid=known",
                ),
            )

        def close(self) -> None:
            self.closed = True

    client = FakeClient()
    exit_code = parser.run(
        [
            "-D",
            str(workdir),
            "-c",
            "--json",
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
        client_factory=lambda: client,
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output[0]["exist"] == "Yes"
    assert client.groups == ["open", "fixed", "invalid"]
    assert client.closed


def test_parser_script_runs_as_a_single_copied_file(tmp_path: Path) -> None:
    copied = tmp_path / "result_parser.py"
    shutil.copy2(SCRIPTS / "result_parser.py", copied)

    completed = subprocess.run(
        [sys.executable, str(copied), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Analyze syzkaller crash reports." in completed.stdout
