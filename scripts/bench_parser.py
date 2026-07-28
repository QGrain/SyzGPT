#!/usr/bin/env python3
"""Robust parser and plotter for syzkaller ``-bench`` logs.

The implementation is designed as a general-purpose command-line tool for
syzkaller-like adjacent-JSON bench logs.

Key properties of this implementation:

* Every run is sampled on an explicit common target-time grid.
* The closest snapshot is selected, which is appropriate for the small uptime
  offsets produced by syzkaller's roughly 60-second bench cadence.
* A snapshot may represent more than one target; targets are never de-duplicated.
* Incomplete curves remain observed-only by default. ``repeat``, ``trend``, and
  an explicit ``auto`` selector are opt-in. Completed portions use the original
  line style;
  ``-D/--debug`` marks them with dashed lines for diagnosis. Exports retain
  provenance metadata in either mode.
* Repeated runs are averaged only where all runs in a group have values, keeping
  a fixed sample count unless the user explicitly completes shorter curves.
* The ``plot`` command can generate VIR with ``--plot-types vir``. VIR computes
  ``100 * new inputs / exec total`` and aligns repeats by coverage milestones;
  its curves always connect to and export ``(0, 0)``.
* Every metric-over-time curve is rendered from the analytical origin
  ``(0, 0)`` without rebasing or modifying the exported observations.
* Plot titles are absent by default for paper use. ``--title`` enables an exact
  user-supplied debugging title, while typography and layout are CLI-controlled.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left
import csv
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Callable, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import EngFormatter, MaxNLocator
import numpy as np

DURATION_TOKEN = re.compile(r"(?P<value>\d+(?:\.\d+)?)(?P<unit>[dhms])")
UNIT_SECONDS = {"d": 86_400.0, "h": 3_600.0, "m": 60.0, "s": 1.0}
DEFAULT_BENCH_CADENCE_SECONDS = 60.0

OKABE_ITO = (
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#000000",
    "#F0E442",
)
MARKERS = ("o", "s", "^", "D", "v", "P", "X", "h")
LINE_STYLES = ("-", "--", "-.", ":")

METRIC_LABELS = {
    "coverage": ("Coverage", "Covered PCs"),
    "signal": ("Signal", "Signal features"),
    "corpus": ("Corpus", "Programs"),
    "syscalls": ("Covered syscalls", "Syscalls"),
    "crash types": ("Unique crashes", "Crash types"),
    "crashes": ("Total crashes", "Crashes"),
    "new inputs": ("Valuable inputs", "Inputs"),
    "exec total": ("Total executions", "Executions"),
}
INTEGER_METRICS = {
    "coverage",
    "signal",
    "corpus",
    "syscalls",
    "crash types",
    "crashes",
    "new inputs",
    "exec total",
}
DEFAULT_PLOT_METRICS = ["coverage", "corpus", "crash types", "exec total"]
DEFAULT_STAT_METRICS = [
    "coverage",
    "signal",
    "corpus",
    "crashes",
    "crash types",
    "new inputs",
    "exec total",
]


@dataclass
class RunSeries:
    name: str
    path: Path
    targets: np.ndarray
    source_uptime: np.ndarray
    observed: np.ndarray
    extrapolated: np.ndarray
    values: dict[str, np.ndarray]
    extension_models: dict[str, str] = field(default_factory=dict)
    nearest_distances: np.ndarray | None = None


@dataclass
class GroupSeries:
    label: str
    targets: np.ndarray
    mean: dict[str, np.ndarray]
    std: dict[str, np.ndarray]
    minimum: dict[str, np.ndarray]
    maximum: dict[str, np.ndarray]
    contributors: dict[str, np.ndarray]
    observed_contributors: np.ndarray
    extrapolated_contributors: np.ndarray
    run_count: int


@dataclass
class VirGroupSeries:
    label: str
    coverage: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    minimum: np.ndarray
    maximum: np.ndarray
    contributors: np.ndarray


@dataclass
class TrendModel:
    name: str
    score: float
    predict_delta: Callable[[np.ndarray], np.ndarray]
    history_points: int


@dataclass
class ExperimentData:
    raw_records: list[list[dict[str, float]]]
    sampled_runs: list[RunSeries]
    grouped_runs: list[tuple[str, Sequence[RunSeries]]]
    grouped_raw: list[tuple[str, Sequence[Sequence[dict[str, float]]]]]
    groups: list[GroupSeries]
    auto_selections: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)


@dataclass(frozen=True)
class PlotStyle:
    """User-configurable publication and screen rendering options."""

    figure_size: tuple[float, float] = (7.4, 4.4)
    font_family: str = "DejaVu Sans"
    font_weight: str = "bold"
    axis_font_size: float = 15.0
    tick_font_size: float = 13.0
    legend_font_size: float = 12.0
    title_font_size: float = 15.0
    line_width: float = 2.2
    marker_size: float = 5.0
    band_alpha: float = 0.14
    grid: bool = True
    grid_alpha: float = 0.65
    markers: bool = True
    legend_location: str = "best"
    legend_columns: int = 0


STYLE_PRESETS: dict[str, PlotStyle] = {
    "paper": PlotStyle(),
    "screen": PlotStyle(
        figure_size=(8.5, 5.0),
        axis_font_size=16.0,
        tick_font_size=14.0,
        legend_font_size=13.0,
        title_font_size=16.0,
        line_width=2.5,
        marker_size=5.5,
    ),
}


def parse_duration(value: str | int | float) -> float:
    """Parse a strict duration such as ``1d2h30m`` or ``1.5h``."""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) < 0:
            raise ValueError("duration cannot be negative")
        return float(value)
    text = str(value).strip().lower()
    if text.isdigit():
        return float(text)
    matches = list(DURATION_TOKEN.finditer(text))
    if not matches or "".join(match.group(0) for match in matches) != text:
        raise ValueError(
            f"invalid duration {value!r}; expected forms like 30m or 1h30m"
        )
    seconds = sum(
        float(match.group("value")) * UNIT_SECONDS[match.group("unit")]
        for match in matches
    )
    if seconds < 0:
        raise ValueError("duration cannot be negative")
    return seconds


def duration_slug(seconds: float) -> str:
    if math.isclose(seconds % 86_400, 0.0):
        return f"{seconds / 86_400:g}d"
    if math.isclose(seconds % 3_600, 0.0):
        return f"{seconds / 3_600:g}h"
    if math.isclose(seconds % 60, 0.0):
        return f"{seconds / 60:g}m"
    return f"{seconds:g}s"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-_")
    return slug or "syzkaller-bench"


def read_bench_log(path: Path) -> list[dict[str, float]]:
    """Read adjacent JSON objects and validate numeric, monotonic uptime."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc

    decoder = json.JSONDecoder()
    records: list[dict[str, float]] = []
    position = 0
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            break
        try:
            record, end = decoder.raw_decode(text, position)
        except json.JSONDecodeError as exc:
            # A live copy may end in one partial object. Corruption before a
            # later complete object is an error rather than a silent gap.
            if text.find("\n{", position + 1) != -1:
                raise ValueError(
                    f"invalid JSON in {path} near byte {exc.pos}: {exc.msg}"
                ) from exc
            print(
                f"warning: ignored an incomplete final JSON object in {path}",
                file=sys.stderr,
            )
            break
        if not isinstance(record, dict):
            raise ValueError(f"expected a JSON object in {path} near byte {position}")
        normalized: dict[str, float] = {}
        for key, raw_value in record.items():
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError(
                    f"non-numeric value for {key!r} in {path} near byte {position}"
                )
            normalized[str(key)] = float(raw_value)
        if "uptime" not in normalized:
            raise ValueError(f"record {len(records)} in {path} has no uptime")
        records.append(normalized)
        position = end

    if not records:
        raise ValueError(f"no complete bench records found in {path}")
    uptimes = [record["uptime"] for record in records]
    for index, (left, right) in enumerate(zip(uptimes, uptimes[1:]), start=1):
        if right < left:
            raise ValueError(
                f"uptime decreases at record {index} in {path}: {left} -> {right}"
            )
    return records


def infer_cadence(records: Sequence[dict[str, float]]) -> float:
    differences = np.diff([record["uptime"] for record in records])
    positive = differences[differences > 0]
    return float(np.median(positive)) if positive.size else 0.0


def infer_sampling_window(
    records: Sequence[dict[str, float]],
) -> tuple[float, float]:
    """Infer cadence-aware matching radii without changing the uptime origin.

    The ordinary nearest-point radius is approximately half one record period,
    with a small allowance for cadence jitter. The same rule applies at the
    beginning, inside the run, and at the end: there is no boundary-specific
    delay or padding rule.
    """

    differences = np.diff([record["uptime"] for record in records])
    positive = differences[differences > 0]
    # A tiny or severely truncated log cannot establish its cadence. Use the
    # documented syzkaller bench default instead of treating one large gap as a
    # genuine recording period.
    if positive.size >= 3:
        cadence = float(np.median(positive))
        jitter = float(np.median(np.abs(positive - cadence)))
    else:
        cadence = DEFAULT_BENCH_CADENCE_SECONDS
        jitter = 0.0
    nearest_radius = max(1.0, cadence / 2.0 + 2.0 * jitter)
    return cadence, nearest_radius


def build_targets(end_seconds: float, interval_seconds: float) -> np.ndarray:
    if end_seconds <= 0:
        raise ValueError("end time must be positive")
    if interval_seconds <= 0:
        raise ValueError("sampling interval must be positive")
    count = int(math.floor(end_seconds / interval_seconds + 1e-12))
    targets = [index * interval_seconds for index in range(count + 1)]
    if not math.isclose(targets[-1], end_seconds, rel_tol=0.0, abs_tol=1e-8):
        targets.append(end_seconds)
    return np.asarray(targets, dtype=float)


def nearest_record_index(uptimes: Sequence[float], target: float) -> int:
    """Return the actual index of the closest uptime; ties prefer the earlier."""

    if not uptimes:
        raise ValueError("cannot sample an empty uptime sequence")
    position = bisect_left(uptimes, target)
    if position <= 0:
        return 0
    if position >= len(uptimes):
        return len(uptimes) - 1
    before = position - 1
    after = position
    if target - uptimes[before] <= uptimes[after] - target:
        return before
    return after


def resample_run(
    path: Path,
    records: Sequence[dict[str, float]],
    targets: np.ndarray,
    metrics: Sequence[str],
) -> RunSeries:
    """Sample absolute uptimes on a target grid without rebasing delayed starts."""

    uptimes = [record["uptime"] for record in records]
    _cadence, nearest_radius = infer_sampling_window(records)
    source_uptime = np.full(targets.shape, np.nan, dtype=float)
    nearest_distances = np.full(targets.shape, np.nan, dtype=float)
    observed = np.zeros(targets.shape, dtype=bool)
    values = {metric: np.full(targets.shape, np.nan, dtype=float) for metric in metrics}

    for target_index, target in enumerate(targets):
        source_index = nearest_record_index(uptimes, float(target))
        distance = abs(uptimes[source_index] - target)
        if distance > nearest_radius:
            continue

        record = records[source_index]
        missing = [metric for metric in metrics if metric not in record]
        if missing:
            raise ValueError(
                f"{path} record at uptime {record['uptime']:g} lacks keys {missing}"
            )
        source_uptime[target_index] = record["uptime"]
        nearest_distances[target_index] = distance
        observed[target_index] = True
        for metric in metrics:
            values[metric][target_index] = record[metric]

    return RunSeries(
        name=path.stem,
        path=path,
        targets=targets.copy(),
        source_uptime=source_uptime,
        observed=observed,
        extrapolated=np.zeros(targets.shape, dtype=bool),
        values=values,
        nearest_distances=nearest_distances,
    )


def conservative_slope_per_hour(x_seconds: np.ndarray, y: np.ndarray) -> float:
    finite = np.isfinite(y)
    x = x_seconds[finite] / 3_600.0
    values = y[finite]
    if values.size < 2:
        return 0.0
    delta_x = np.diff(x)
    slopes = np.diff(values) / delta_x
    positive = slopes[np.isfinite(slopes) & (slopes > 0)]
    if positive.size == 0:
        return 0.0
    return float(np.quantile(positive, 0.25))


def _prepare_trend_history(
    x_seconds: np.ndarray, y_values: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return sorted, unique, monotonic observations in elapsed hours."""

    finite = np.isfinite(x_seconds) & np.isfinite(y_values)
    x = np.asarray(x_seconds[finite], dtype=float)
    y = np.asarray(y_values[finite], dtype=float)
    if x.size == 0:
        return x, y
    order = np.argsort(x, kind="stable")
    x = x[order]
    y = np.maximum.accumulate(y[order])
    # Keep the last value at a duplicate uptime; cumulative metrics make it the
    # most informative representation of that instant.
    keep = np.concatenate((np.diff(x) > 0, np.asarray([True])))
    x = x[keep] / 3_600.0
    y = y[keep]
    x -= x[0]
    return x, y


def _endpoint_growth_rate(x_hours: np.ndarray, y: np.ndarray) -> float:
    """Estimate a stable local derivative for a slope-continuous join."""

    if y.size < 2 or x_hours[-1] <= x_hours[0]:
        return 0.0
    span = float(x_hours[-1] - x_hours[0])
    lookback = min(3.0, max(0.5, 0.25 * span))
    start = int(np.searchsorted(x_hours, x_hours[-1] - lookback, side="left"))
    if y.size - start < 4:
        start = max(0, y.size - min(12, y.size))
    local_x = x_hours[start:] - x_hours[-1]
    local_y = y[start:]
    centered_x = local_x - float(np.mean(local_x))
    centered_y = local_y - float(np.mean(local_y))
    denominator = float(np.dot(centered_x, centered_x))
    if denominator <= 0:
        return 0.0
    slope = float(np.dot(centered_x, centered_y) / denominator)
    return max(0.0, slope)


def _fit_damped_rate_shape(
    x_hours: np.ndarray, y: np.ndarray, decay: float
) -> tuple[float, float] | None:
    """Fit ``floor + transient*exp(-decay*t)`` as a cumulative curve."""

    if decay <= 0:
        design = np.column_stack((np.ones(x_hours.size), x_hours))
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        if not np.all(np.isfinite(coefficients)):
            return None
        return max(0.0, float(coefficients[1])), 0.0

    transient_feature = -np.expm1(-decay * x_hours) / decay
    design = np.column_stack((np.ones(x_hours.size), x_hours, transient_feature))
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    if not np.all(np.isfinite(coefficients)):
        return None
    floor = float(coefficients[1])
    transient = float(coefficients[2])

    # A genuinely saturating curve often gives a slightly negative unrestricted
    # floor. Refit it with the physically meaningful floor fixed at zero.
    if floor < 0:
        reduced = np.column_stack((np.ones(x_hours.size), transient_feature))
        reduced_coefficients, *_ = np.linalg.lstsq(reduced, y, rcond=None)
        if not np.all(np.isfinite(reduced_coefficients)):
            return None
        floor = 0.0
        transient = float(reduced_coefficients[1])
    if transient < 0:
        return None
    return floor, transient


def _damped_growth_delta(
    elapsed_hours: np.ndarray,
    start_rate: float,
    floor_rate: float,
    decay: float,
) -> np.ndarray:
    """Integrate a non-negative rate that smoothly decays from the endpoint."""

    elapsed = np.maximum(np.asarray(elapsed_hours, dtype=float), 0.0)
    start = max(0.0, float(start_rate))
    floor = min(start, max(0.0, float(floor_rate)))
    if decay <= 1e-12:
        return start * elapsed
    return floor * elapsed + (start - floor) * (-np.expm1(-decay * elapsed)) / decay


def _rolling_cut_indices(x_hours: np.ndarray) -> list[int]:
    """Choose deterministic historical cut points with usable suffixes."""

    if x_hours.size < 4:
        return []
    span = max(float(x_hours[-1]), 1e-6)
    indices = sorted(
        {
            min(
                x_hours.size - 2,
                max(
                    3,
                    int(np.searchsorted(x_hours, fraction * span, side="right") - 1),
                ),
            )
            for fraction in (0.50, 0.65, 0.80)
        }
    )
    return [
        index
        for index in indices
        if index >= 3 and np.count_nonzero(x_hours > x_hours[index]) >= 2
    ]


def _linear_rate_trend_model(
    x_hours: np.ndarray,
    y: np.ndarray,
    score: float = float("inf"),
) -> TrendModel:
    """Return the zero-decay member of the trend model family."""

    rate = _endpoint_growth_rate(x_hours, y)
    if rate <= 0 and y.size >= 2:
        rate = conservative_slope_per_hour(x_hours * 3_600.0, y)
    return TrendModel(
        name=f"linear-rate(start={rate:g}/h)",
        score=score,
        predict_delta=lambda elapsed: rate
        * np.maximum(np.asarray(elapsed, dtype=float), 0.0),
        history_points=int(y.size),
    )


def fit_trend_model(
    x_seconds: np.ndarray,
    y_values: np.ndarray,
    forecast_hours: float,
) -> TrendModel:
    """Fit an endpoint-continuous growth-rate model using all observations.

    Candidate decay rates are evaluated at several historical cut points. Each
    fold fits its entire prefix and predicts the following horizon. The final
    model is refit on the complete history, then anchored at the last observed
    value with a robust local derivative. The zero-decay linear rate is part of
    this trend family; this function never switches to another completion mode.
    """

    x, y = _prepare_trend_history(x_seconds, y_values)
    if y.size < 4:
        return _linear_rate_trend_model(x, y)

    span = max(float(x[-1]), 1e-6)
    horizon = max(float(forecast_hours), 0.25)
    decay_candidates = [0.0, *[factor / span for factor in (0.25, 0.5, 1, 2, 4, 8)]]
    cut_indices = _rolling_cut_indices(x)
    if not cut_indices:
        return _linear_rate_trend_model(x, y)

    fold_count = 0
    candidate_scores: dict[float, list[float]] = {
        decay: [] for decay in decay_candidates
    }
    total_growth = max(float(y[-1] - y[0]), 1.0)
    for cut_index in cut_indices:
        validation = np.flatnonzero((x > x[cut_index]) & (x <= x[cut_index] + horizon))
        if validation.size < 2:
            validation = np.arange(cut_index + 1, y.size)
        if validation.size == 0:
            continue
        fold_count += 1
        validation_x = x[validation] - x[cut_index]
        validation_y = y[validation]
        normalizer = max(
            float(validation_y[-1] - y[cut_index]),
            0.05 * total_growth,
            1.0,
        )
        prefix_x = x[: cut_index + 1]
        prefix_y = y[: cut_index + 1]
        start_rate = _endpoint_growth_rate(prefix_x, prefix_y)
        for decay in decay_candidates:
            shape = _fit_damped_rate_shape(prefix_x, prefix_y, decay)
            if shape is None:
                continue
            floor_rate, _transient = shape
            prediction = y[cut_index] + _damped_growth_delta(
                validation_x, start_rate, floor_rate, decay
            )
            rmse = float(np.sqrt(np.mean((prediction - validation_y) ** 2)))
            candidate_scores[decay].append(rmse / normalizer)

    eligible = {
        decay: float(np.mean(scores))
        for decay, scores in candidate_scores.items()
        if len(scores) == fold_count and scores
    }
    if not eligible:
        return _linear_rate_trend_model(x, y)

    final_shapes = {
        decay: shape
        for decay in eligible
        if (shape := _fit_damped_rate_shape(x, y, decay)) is not None
    }
    if not final_shapes:
        return _linear_rate_trend_model(x, y)

    best_decay, best_score = min(
        ((decay, score) for decay, score in eligible.items() if decay in final_shapes),
        key=lambda item: item[1],
    )
    final_shape = final_shapes[best_decay]
    floor_rate, _transient = final_shape
    start_rate = _endpoint_growth_rate(x, y)
    effective_floor = min(start_rate, floor_rate)
    name = (
        f"linear-rate(start={start_rate:g}/h)"
        if best_decay <= 0
        else (
            f"damped-rate(decay={best_decay:g}/h,start={start_rate:g}/h,"
            f"floor={effective_floor:g}/h)"
        )
    )
    return TrendModel(
        name=name,
        score=best_score,
        predict_delta=lambda elapsed: _damped_growth_delta(
            np.asarray(elapsed, dtype=float),
            start_rate,
            effective_floor,
            best_decay,
        ),
        history_points=int(y.size),
    )


def _metric_history(
    series: RunSeries,
    raw_records: Sequence[dict[str, float]] | None,
    metric: str,
) -> tuple[np.ndarray, np.ndarray, str, int] | None:
    """Get all usable observations through the last sampled real record."""

    values = series.values[metric]
    finite_observed = np.flatnonzero(series.observed & np.isfinite(values))
    if finite_observed.size == 0:
        return None
    last_index = int(finite_observed[-1])
    history_x = series.targets[: last_index + 1]
    history_y = values[: last_index + 1]
    source = "sampled"
    source_uptime = series.source_uptime[last_index]
    if raw_records is not None and np.isfinite(source_uptime):
        raw_history = [
            record
            for record in raw_records
            if record["uptime"] <= source_uptime and metric in record
        ]
        if len(raw_history) >= 4:
            history_x = np.asarray(
                [record["uptime"] for record in raw_history], dtype=float
            )
            history_y = np.asarray(
                [record[metric] for record in raw_history], dtype=float
            )
            source = "raw"
    return history_x, history_y, source, last_index


def score_completion_method(
    x_seconds: np.ndarray,
    y_values: np.ndarray,
    forecast_hours: float,
    method: str,
) -> float:
    """Rolling-origin normalized RMSE for one deterministic completion method."""

    if method not in {"repeat", "trend"}:
        raise ValueError(f"unsupported auto candidate {method!r}")
    x, y = _prepare_trend_history(x_seconds, y_values)
    cut_indices = _rolling_cut_indices(x)
    if not cut_indices:
        return float("inf")

    horizon = max(float(forecast_hours), 0.25)
    total_growth = max(float(y[-1] - y[0]), 1.0)
    scores: list[float] = []
    for cut_index in cut_indices:
        validation = np.flatnonzero((x > x[cut_index]) & (x <= x[cut_index] + horizon))
        if validation.size < 2:
            validation = np.arange(cut_index + 1, y.size)
        if validation.size == 0:
            continue
        elapsed = x[validation] - x[cut_index]
        prefix_x = x[: cut_index + 1]
        prefix_y = y[: cut_index + 1]

        if method == "repeat":
            delta = np.zeros(elapsed.shape, dtype=float)
        else:
            model = fit_trend_model(
                prefix_x * 3_600.0,
                prefix_y,
                min(horizon, float(elapsed[-1])),
            )
            delta = model.predict_delta(elapsed)

        validation_y = y[validation]
        prediction = y[cut_index] + delta
        normalizer = max(
            float(validation_y[-1] - y[cut_index]),
            0.05 * total_growth,
            1.0,
        )
        rmse = float(np.sqrt(np.mean((prediction - validation_y) ** 2)))
        scores.append(rmse / normalizer)
    return float(np.mean(scores)) if scores else float("inf")


def select_auto_completion(
    runs: Sequence[RunSeries],
    raw_runs: Sequence[Sequence[dict[str, float]]],
    metrics: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Select one method per fuzzer metric using repeat-equal backtesting."""

    if len(runs) != len(raw_runs):
        raise ValueError("auto selection requires one raw log per sampled run")
    candidates = ("repeat", "trend")
    decisions: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        histories: list[tuple[RunSeries, np.ndarray, np.ndarray, str, float]] = []
        positive_horizons: list[float] = []
        for run, records in zip(runs, raw_runs):
            history = _metric_history(run, records, metric)
            if history is None:
                continue
            history_x, history_y, source, last_index = history
            completion_horizon = max(
                0.0,
                float((run.targets[-1] - run.targets[last_index]) / 3_600.0),
            )
            if completion_horizon > 0:
                positive_horizons.append(completion_horizon)
            histories.append((run, history_x, history_y, source, completion_horizon))

        if not histories:
            continue
        if positive_horizons:
            validation_horizon = max(positive_horizons)
        elif runs[0].targets.size >= 2:
            validation_horizon = float(np.median(np.diff(runs[0].targets)) / 3_600.0)
        else:
            validation_horizon = 1.0

        run_scores: list[dict[str, Any]] = []
        method_scores: dict[str, list[float]] = {
            candidate: [] for candidate in candidates
        }
        for run, history_x, history_y, source, _completion_horizon in histories:
            per_run: dict[str, Any] = {
                "run": run.name,
                "path": str(run.path),
                "history_source": source,
            }
            for candidate in candidates:
                score = score_completion_method(
                    history_x,
                    history_y,
                    validation_horizon,
                    candidate,
                )
                per_run[candidate] = score if np.isfinite(score) else None
                if np.isfinite(score):
                    method_scores[candidate].append(score)
            run_scores.append(per_run)

        aggregated = {
            candidate: (float(np.mean(scores)) if scores else float("inf"))
            for candidate, scores in method_scores.items()
        }
        best_score = min(aggregated.values())
        if not np.isfinite(best_score):
            selected = "repeat"
        else:
            tolerance = max(1e-12, 0.05 * best_score)
            selected = next(
                candidate
                for candidate in candidates
                if aggregated[candidate] <= best_score + tolerance
            )
        decisions[metric] = {
            "selected": selected,
            "rolling_nrmse": {
                candidate: (score if np.isfinite(score) else None)
                for candidate, score in aggregated.items()
            },
            "validation_horizon_hours": validation_horizon,
            "tie_tolerance": "within 5% of best; prefer repeat, then trend",
            "run_scores": run_scores,
        }
    return decisions


def extend_run_tail(
    series: RunSeries,
    mode: str,
    raw_records: Sequence[dict[str, float]] | None = None,
    metric_modes: dict[str, str] | None = None,
) -> None:
    if mode == "none":
        return
    observed_indices = np.flatnonzero(series.observed)
    if observed_indices.size == 0:
        return
    last_observed = int(observed_indices[-1])
    tail_indices = np.arange(last_observed + 1, series.targets.size)
    if tail_indices.size == 0:
        return

    for metric, values in series.values.items():
        finite_observed = np.flatnonzero(series.observed & np.isfinite(values))
        if finite_observed.size == 0:
            continue
        effective_mode = (
            metric_modes.get(metric, "")
            if mode == "auto" and metric_modes is not None
            else mode
        )
        if mode == "auto" and not effective_mode:
            raise ValueError(f"auto has no selected method for metric {metric!r}")
        last_index = int(finite_observed[-1])
        metric_tail = np.arange(last_index + 1, series.targets.size)
        if metric_tail.size == 0:
            continue
        last_value = float(values[last_index])
        last_time_hours = float(series.targets[last_index] / 3_600.0)
        model_description: str

        if effective_mode == "repeat":
            values[metric_tail] = last_value
            model_description = "repeat-last"

        elif effective_mode == "trend":
            history = _metric_history(series, raw_records, metric)
            if history is None:
                continue
            history_x, history_y, source, _history_last_index = history
            forecast_hours = float(series.targets[-1] / 3_600.0 - last_time_hours)
            model = fit_trend_model(
                history_x,
                history_y,
                forecast_hours,
            )
            elapsed_hours = series.targets[metric_tail] / 3_600.0 - last_time_hours
            values[metric_tail] = last_value + model.predict_delta(elapsed_hours)
            model_description = (
                f"trend({model.name},rolling-nrmse={model.score:g},"
                f"source={source},points={model.history_points})"
            )
        else:
            raise ValueError(f"unknown curve-completion mode {effective_mode!r}")

        series.extension_models[metric] = (
            f"auto->{model_description}" if mode == "auto" else model_description
        )

    series.extrapolated[tail_indices] = True


def aggregate_group(
    label: str, runs: Sequence[RunSeries], metrics: Sequence[str]
) -> GroupSeries:
    if not runs:
        raise ValueError(f"group {label!r} contains no runs")
    targets = runs[0].targets
    if any(not np.array_equal(run.targets, targets) for run in runs[1:]):
        raise ValueError(f"group {label!r} does not share one target grid")

    mean: dict[str, np.ndarray] = {}
    std: dict[str, np.ndarray] = {}
    minimum: dict[str, np.ndarray] = {}
    maximum: dict[str, np.ndarray] = {}
    contributors: dict[str, np.ndarray] = {}

    observed_contributors = np.sum(np.vstack([run.observed for run in runs]), axis=0)
    extrapolated_contributors = np.sum(
        np.vstack([run.extrapolated for run in runs]), axis=0
    )
    for metric in metrics:
        matrix = np.vstack([run.values[metric] for run in runs])
        finite = np.isfinite(matrix)
        counts = finite.sum(axis=0)
        contributors[metric] = counts
        complete = counts == len(runs)
        metric_mean = np.full(targets.shape, np.nan)
        metric_std = np.full(targets.shape, np.nan)
        metric_min = np.full(targets.shape, np.nan)
        metric_max = np.full(targets.shape, np.nan)
        if np.any(complete):
            complete_values = matrix[:, complete]
            metric_mean[complete] = np.mean(complete_values, axis=0)
            metric_std[complete] = np.std(complete_values, axis=0, ddof=0)
            metric_min[complete] = np.min(complete_values, axis=0)
            metric_max[complete] = np.max(complete_values, axis=0)
        mean[metric] = metric_mean
        std[metric] = metric_std
        minimum[metric] = metric_min
        maximum[metric] = metric_max

    return GroupSeries(
        label=label,
        targets=targets.copy(),
        mean=mean,
        std=std,
        minimum=minimum,
        maximum=maximum,
        contributors=contributors,
        observed_contributors=observed_contributors,
        extrapolated_contributors=extrapolated_contributors,
        run_count=len(runs),
    )


def nice_step(raw_step: float) -> float:
    if raw_step <= 0:
        return 1.0
    exponent = math.floor(math.log10(raw_step))
    fraction = raw_step / (10**exponent)
    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    return nice_fraction * (10**exponent)


def raw_vir_curve(
    records: Sequence[dict[str, float]],
    end_seconds: float,
    numerator: str,
    denominator: str,
) -> tuple[np.ndarray, np.ndarray]:
    required = ("coverage", numerator, denominator)
    points: dict[float, float] = {}
    maximum_coverage = 0.0
    uptimes = [record["uptime"] for record in records]
    end_index = nearest_record_index(uptimes, end_seconds)
    _cadence, nearest_radius = infer_sampling_window(records)
    if end_seconds < uptimes[0] and uptimes[0] - end_seconds > nearest_radius:
        raise ValueError("requested VIR end time precedes the first supported record")
    # The nearest record may be slightly later than the requested time, which
    # is intentional for jittered periodic snapshots.
    for record in records[: end_index + 1]:
        missing = [key for key in required if key not in record]
        if missing:
            raise ValueError(f"VIR record at {record['uptime']:g}s lacks {missing}")
        maximum_coverage = max(maximum_coverage, record["coverage"])
        denominator_value = record[denominator]
        ratio = (
            0.0
            if denominator_value <= 0
            else 100.0 * record[numerator] / denominator_value
        )
        # Use accumulated coverage so occasional decreases do not reverse the
        # coverage-domain interpolation. Keep the latest VIR at a plateau.
        points[maximum_coverage] = ratio
    if len(points) < 2:
        raise ValueError("not enough VIR points within the requested time")
    coverage = np.asarray(sorted(points), dtype=float)
    vir = np.asarray([points[value] for value in coverage], dtype=float)
    return coverage, vir


def aggregate_vir_group(
    label: str,
    runs: Sequence[Sequence[dict[str, float]]],
    end_seconds: float,
    numerator: str,
    denominator: str,
    coverage_step: float,
) -> VirGroupSeries:
    curves = [raw_vir_curve(run, end_seconds, numerator, denominator) for run in runs]
    lower = max(curve[0][0] for curve in curves)
    upper = min(curve[0][-1] for curve in curves)
    if upper <= lower:
        raise ValueError(f"VIR runs for {label!r} have no common coverage range")
    start = math.ceil(lower / coverage_step) * coverage_step
    stop = math.floor(upper / coverage_step) * coverage_step
    grid = np.arange(start, stop + coverage_step * 0.5, coverage_step, dtype=float)
    if grid.size < 2:
        grid = np.linspace(lower, upper, 3)
    matrix = np.vstack([np.interp(grid, coverage, vir) for coverage, vir in curves])
    mean = np.mean(matrix, axis=0)
    std = np.std(matrix, axis=0, ddof=0)
    minimum = np.min(matrix, axis=0)
    maximum = np.max(matrix, axis=0)
    contributors = np.full(grid.shape, len(runs), dtype=int)

    # A VIR curve conventionally emerges from the coordinate origin. Add the
    # analytical baseline after averaging so observed values still use only the
    # common coverage domain. This row is also exported to CSV.
    if grid[0] > 0:
        grid = np.insert(grid, 0, 0.0)
        mean = np.insert(mean, 0, 0.0)
        std = np.insert(std, 0, 0.0)
        minimum = np.insert(minimum, 0, 0.0)
        maximum = np.insert(maximum, 0, 0.0)
        contributors = np.insert(contributors, 0, len(runs))
    else:
        # The origin is an analytical baseline. If the common observed domain
        # already begins at zero coverage, render/export that first coordinate
        # as (0, 0) instead of exposing a nonzero ratio at the origin.
        mean[0] = 0.0
        std[0] = 0.0
        minimum[0] = 0.0
        maximum[0] = 0.0

    return VirGroupSeries(
        label=label,
        coverage=grid,
        mean=mean,
        std=std,
        minimum=minimum,
        maximum=maximum,
        contributors=contributors,
    )


def configure_style(style: PlotStyle | None = None) -> None:
    style = style or PlotStyle()
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [style.font_family, "DejaVu Sans", "Arial", "Helvetica"],
            "font.size": style.tick_font_size,
            "axes.labelsize": style.axis_font_size,
            "axes.labelweight": style.font_weight,
            "axes.titlesize": style.title_font_size,
            "axes.titleweight": style.font_weight,
            "xtick.labelsize": style.tick_font_size,
            "ytick.labelsize": style.tick_font_size,
            "legend.fontsize": style.legend_font_size,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
        }
    )


def x_ticks(hours: float, interval_count: int) -> np.ndarray:
    return np.linspace(0.0, hours, interval_count + 1)


def apply_axis_typography(ax: plt.Axes, style: PlotStyle) -> None:
    """Apply explicit sizes/weights so text remains legible after downscaling."""

    ax.xaxis.label.set_fontsize(style.axis_font_size)
    ax.yaxis.label.set_fontsize(style.axis_font_size)
    ax.xaxis.label.set_fontweight(style.font_weight)
    ax.yaxis.label.set_fontweight(style.font_weight)
    for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        label.set_fontsize(style.tick_font_size)
        label.set_fontweight(style.font_weight)


def style_time_axis(
    ax: plt.Axes,
    hours: float,
    x_tick_intervals: int,
    metric: str,
    style: PlotStyle,
) -> None:
    ax.set_xlim(0.0, hours)
    ax.set_ylim(bottom=0.0)
    ticks = x_ticks(hours, x_tick_intervals)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{tick:g}" for tick in ticks])
    ax.set_xlabel("Time (hours)")
    if metric in {"crash types", "crashes"}:
        ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=4))
    else:
        ax.yaxis.set_major_formatter(EngFormatter(places=0, sep=""))
    if style.grid:
        ax.grid(True, color="#D9D9D9", linewidth=0.65, alpha=style.grid_alpha)
    else:
        ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)
    apply_axis_typography(ax, style)


def metric_title_and_label(metric: str) -> tuple[str, str]:
    return METRIC_LABELS.get(metric, (metric.replace("_", " ").title(), metric))


def plot_metric(
    groups: Sequence[GroupSeries],
    metric: str,
    hours: float,
    x_tick_intervals: int,
    title: str | None,
    error_band: str,
    style: PlotStyle | None = None,
    debug: bool = False,
) -> plt.Figure:
    style = style or PlotStyle()
    fig, ax = plt.subplots(figsize=style.figure_size)
    any_extrapolated = False
    for index, group in enumerate(groups):
        color = OKABE_ITO[index % len(OKABE_ITO)]
        marker = MARKERS[index % len(MARKERS)]
        x = group.targets / 3_600.0
        y = group.mean[metric].copy()
        finite = np.isfinite(y)
        extrapolated = finite & (group.extrapolated_contributors > 0)
        observed_mean = finite & ~extrapolated

        first_finite = np.flatnonzero(finite)
        if first_finite.size and math.isclose(x[first_finite[0]], 0.0):
            y[first_finite[0]] = 0.0

        if error_band != "none":
            if error_band == "sd":
                lower = y - group.std[metric]
                upper = y + group.std[metric]
            else:
                lower = group.minimum[metric].copy()
                upper = group.maximum[metric].copy()
            if first_finite.size and math.isclose(x[first_finite[0]], 0.0):
                lower[first_finite[0]] = 0.0
                upper[first_finite[0]] = 0.0
            ax.fill_between(
                x, lower, upper, where=finite, color=color, alpha=style.band_alpha
            )

        primary = observed_mean if debug else finite
        primary_indices = np.flatnonzero(primary)
        if primary_indices.size:
            # Keep NaNs on the canonical grid so matplotlib breaks the line at
            # an internal missing-data gap instead of visually bridging it.
            first_primary = int(primary_indices[0])
            primary_x = x[first_primary:].copy()
            primary_y = np.where(primary[first_primary:], y[first_primary:], np.nan)
            if primary_x[0] > 0:
                primary_x = np.insert(primary_x, 0, 0.0)
                primary_y = np.insert(primary_y, 0, 0.0)
            ax.plot(
                primary_x,
                primary_y,
                label=group.label,
                color=color,
                linestyle="-",
                marker=marker if style.markers else None,
                markerfacecolor="white",
                markeredgewidth=0.7,
                markersize=style.marker_size,
                linewidth=style.line_width,
            )
        else:
            # Ensure every group remains represented in the legend.
            ax.plot(
                [],
                [],
                label=group.label,
                color=color,
                marker=marker if style.markers else None,
            )

        extrapolated_indices = np.flatnonzero(extrapolated)
        if debug and extrapolated_indices.size:
            any_extrapolated = True
            first = int(extrapolated_indices[0])
            connector = first - 1 if first > 0 and finite[first - 1] else first
            segment = np.arange(connector, int(extrapolated_indices[-1]) + 1)
            ax.plot(
                x[segment],
                y[segment],
                color=color,
                linestyle="--",
                linewidth=style.line_width,
                alpha=0.85,
            )

    _panel_title, y_label = metric_title_and_label(metric)
    if title:
        ax.set_title(
            title,
            fontsize=style.title_font_size,
            fontweight=style.font_weight,
        )
    ax.set_ylabel(y_label)
    style_time_axis(ax, hours, x_tick_intervals, metric, style)
    handles, labels = ax.get_legend_handles_labels()
    if debug and any_extrapolated:
        handles.append(
            Line2D(
                [0],
                [0],
                color="#555555",
                linestyle="--",
                linewidth=style.line_width,
            )
        )
        labels.append("Extrapolated mean")
    legend_columns = style.legend_columns or min(3, len(labels))
    ax.legend(
        handles,
        labels,
        frameon=False,
        ncol=legend_columns,
        loc=style.legend_location,
        prop={"size": style.legend_font_size, "weight": style.font_weight},
    )
    fig.tight_layout()
    return fig


def plot_vir(
    groups: Sequence[VirGroupSeries],
    title: str | None,
    error_band: str,
    style: PlotStyle | None = None,
) -> plt.Figure:
    style = style or PlotStyle()
    fig, ax = plt.subplots(figsize=style.figure_size)
    for index, group in enumerate(groups):
        color = OKABE_ITO[index % len(OKABE_ITO)]
        marker = MARKERS[index % len(MARKERS)]
        if error_band != "none":
            if error_band == "sd":
                lower = group.mean - group.std
                upper = group.mean + group.std
            else:
                lower = group.minimum
                upper = group.maximum
            ax.fill_between(
                group.coverage, lower, upper, color=color, alpha=style.band_alpha
            )
        ax.plot(
            group.coverage,
            group.mean,
            label=group.label,
            color=color,
            linestyle=LINE_STYLES[index % len(LINE_STYLES)],
            marker=marker if style.markers else None,
            markerfacecolor="white",
            markeredgewidth=0.7,
            markersize=style.marker_size,
            linewidth=style.line_width,
        )
    if title:
        ax.set_title(
            title,
            fontsize=style.title_font_size,
            fontweight=style.font_weight,
        )
    ax.set_xlabel("Coverage")
    ax.set_ylabel("VIR (%)")
    ax.set_ylim(bottom=0.0)
    ax.set_xlim(left=0.0)
    ax.xaxis.set_major_formatter(EngFormatter(places=0, sep=""))
    if style.grid:
        ax.grid(True, color="#D9D9D9", linewidth=0.65, alpha=style.grid_alpha)
    else:
        ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    apply_axis_typography(ax, style)
    legend_columns = style.legend_columns or min(3, len(groups))
    ax.legend(
        frameon=False,
        ncol=legend_columns,
        loc=style.legend_location,
        prop={"size": style.legend_font_size, "weight": style.font_weight},
    )
    fig.tight_layout()
    return fig


def save_figure(
    fig: plt.Figure, base_path: Path, formats: Iterable[str], dpi: int
) -> list[Path]:
    written: list[Path] = []
    for file_format in formats:
        path = base_path.with_suffix(f".{file_format}")
        options: dict[str, Any] = {
            "bbox_inches": "tight",
            "pad_inches": 0.08,
            "metadata": {"Creator": "scripts/bench_parser.py"},
        }
        if file_format == "png":
            options["dpi"] = dpi
        fig.savefig(path, **options)
        written.append(path)
    plt.close(fig)
    return written


def write_run_samples_csv(
    path: Path,
    grouped_runs: Sequence[tuple[str, Sequence[RunSeries]]],
    metrics: Sequence[str],
) -> None:
    fields = [
        "group",
        "run",
        "target_hours",
        "source_uptime_seconds",
        "nearest_distance_seconds",
        "observed",
        "extrapolated",
        *metrics,
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for label, runs in grouped_runs:
            for run in runs:
                for index, target in enumerate(run.targets):
                    row: dict[str, Any] = {
                        "group": label,
                        "run": run.name,
                        "target_hours": f"{target / 3_600:g}",
                        "source_uptime_seconds": (
                            ""
                            if not np.isfinite(run.source_uptime[index])
                            else run.source_uptime[index]
                        ),
                        "nearest_distance_seconds": (
                            ""
                            if run.nearest_distances is None
                            or not np.isfinite(run.nearest_distances[index])
                            else run.nearest_distances[index]
                        ),
                        "observed": int(run.observed[index]),
                        "extrapolated": int(run.extrapolated[index]),
                    }
                    for metric in metrics:
                        value = run.values[metric][index]
                        row[metric] = "" if not np.isfinite(value) else value
                    writer.writerow(row)


def write_group_csv(
    path: Path, groups: Sequence[GroupSeries], metrics: Sequence[str]
) -> None:
    fields = [
        "group",
        "target_hours",
        "metric",
        "mean",
        "std",
        "min",
        "max",
        "contributors",
        "observed_contributors",
        "extrapolated_contributors",
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for group in groups:
            for metric in metrics:
                for index, target in enumerate(group.targets):
                    value = group.mean[metric][index]
                    if not np.isfinite(value):
                        continue
                    writer.writerow(
                        {
                            "group": group.label,
                            "target_hours": f"{target / 3_600:g}",
                            "metric": metric,
                            "mean": value,
                            "std": group.std[metric][index],
                            "min": group.minimum[metric][index],
                            "max": group.maximum[metric][index],
                            "contributors": group.contributors[metric][index],
                            "observed_contributors": group.observed_contributors[index],
                            "extrapolated_contributors": group.extrapolated_contributors[
                                index
                            ],
                        }
                    )


def write_vir_csv(path: Path, groups: Sequence[VirGroupSeries]) -> None:
    fields = [
        "group",
        "coverage",
        "vir_mean_percent",
        "vir_std",
        "vir_min",
        "vir_max",
        "contributors",
        "is_origin",
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for group in groups:
            for index, coverage in enumerate(group.coverage):
                writer.writerow(
                    {
                        "group": group.label,
                        "coverage": coverage,
                        "vir_mean_percent": group.mean[index],
                        "vir_std": group.std[index],
                        "vir_min": group.minimum[index],
                        "vir_max": group.maximum[index],
                        "contributors": group.contributors[index],
                        "is_origin": int(coverage == 0 and group.mean[index] == 0),
                    }
                )


class DetailedHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    """Show useful defaults without cluttering help with empty sentinel values."""

    def _get_help_string(self, action: argparse.Action) -> str:
        default = action.default
        if (
            default is None
            or default is False
            or default is argparse.SUPPRESS
            or default == []
            or default == ()
        ):
            return action.help
        return super()._get_help_string(action)


def _add_experiment_arguments(
    parser: argparse.ArgumentParser, default_metrics: Sequence[str]
) -> None:
    inputs = parser.add_argument_group("experiment input")
    inputs.add_argument(
        "-b",
        "--bench-file",
        nargs="+",
        type=Path,
        required=True,
        metavar="LOG",
        help="logs ordered by fuzzer, then by repeat",
    )
    inputs.add_argument(
        "-a",
        "--repeats",
        type=int,
        default=1,
        metavar="N",
        help="number of consecutive repeated runs in each fuzzer group",
    )
    inputs.add_argument(
        "-l",
        "--labels",
        nargs="+",
        metavar="LABEL",
        help="one fuzzer label per group; defaults to the first run filename",
    )
    inputs.add_argument(
        "-k",
        "--metrics",
        nargs="+",
        default=list(default_metrics),
        metavar="METRIC",
        help="bench metrics to analyze",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    show_advanced = "--help-all" in raw_argv

    def advanced_help(text: str) -> str:
        return text if show_advanced else argparse.SUPPRESS

    parser = argparse.ArgumentParser(
        description="Analyze or plot syzkaller-like adjacent-JSON bench logs.",
        epilog=(
            "Run 'bench_parser.py stat --help' or 'bench_parser.py plot --help' "
            "for command-specific options."
        ),
        formatter_class=DetailedHelpFormatter,
    )
    commands = parser.add_subparsers(
        dest="command", metavar="{stat,plot}", required=True
    )

    stat_parser = commands.add_parser(
        "stat",
        help="print observed metrics and log-health summaries",
        description=(
            "Report observed values at one or more target uptimes. Repeated runs "
            "are summarized per fuzzer with mean, standard deviation, range, "
            "and contributor count. Partial means are clearly labeled by their "
            "available/expected run count. No extrapolation or figures are produced."
        ),
        formatter_class=DetailedHelpFormatter,
    )
    _add_experiment_arguments(stat_parser, DEFAULT_STAT_METRICS)
    stat_parser.add_argument(
        "-t",
        "--time",
        dest="times",
        nargs="+",
        default=["24h"],
        metavar="TIME",
        help="one or more target uptimes",
    )
    stat_parser.add_argument(
        "--show-runs",
        action="store_true",
        help="also print the selected source record and metrics for every run",
    )
    stat_parser.epilog = """
Examples:
  bench_parser.py stat -b run-a.log run-b.log -l Fuzzer-A Fuzzer-B -t 24h

  bench_parser.py stat -b a{1..5}.log b{1..5}.log -a 5 -l A B \\
    -t 6h 12h 24h -k coverage crashes 'crash types' 'exec total'

Sampling semantics:
  Uptime is never rebased. A first record at 122s may represent a nearby 120s
  target, but never 0s. Matching windows are inferred from each log's cadence.
"""

    plot_parser = commands.add_parser(
        "plot",
        help="generate time-series and/or VIR figures",
        description=(
            "Align repeated runs on explicit target grids and generate figures "
            "plus machine-readable CSV/JSON provenance."
        ),
        formatter_class=DetailedHelpFormatter,
    )
    _add_experiment_arguments(plot_parser, DEFAULT_PLOT_METRICS)
    plot_parser.add_argument(
        "--help-all",
        action="help",
        help="show common and advanced plot options, then exit",
    )

    sampling = plot_parser.add_argument_group("time range and figure selection")
    sampling.add_argument(
        "-t", "--time", default="24h", metavar="DURATION", help="requested end time"
    )
    sampling.add_argument(
        "-i",
        "--interval",
        default="1h",
        metavar="DURATION",
        help="time-series target-grid interval",
    )
    sampling.add_argument(
        "--plot-types",
        nargs="+",
        choices=("time", "vir"),
        default=("time",),
        metavar="{time,vir}",
        help="figures to generate: metric-over-time, VIR-over-coverage, or both",
    )

    output = plot_parser.add_argument_group("output")
    output.add_argument(
        "-o", "--out-dir", type=Path, default=Path("."), help="output directory"
    )
    output.add_argument(
        "--formats",
        nargs="+",
        choices=("png", "pdf", "svg"),
        default=("png", "pdf"),
        help="figure formats",
    )
    output.add_argument(
        "--dpi",
        type=int,
        default=300,
        help=advanced_help("PNG resolution; used only when png is in --formats"),
    )
    output.add_argument(
        "--filename-prefix",
        help="filename prefix; otherwise title or 'syzkaller-bench' is used",
    )

    completion = plot_parser.add_argument_group("curve completion extension")
    completion.add_argument(
        "--curve-completion",
        choices=("none", "repeat", "trend", "auto"),
        default="none",
        help=(
            "complete time-series runs ending before --time: none, repeat last "
            "value, a pure growth-rate trend, or group-level automatic selection"
        ),
    )

    vir = plot_parser.add_argument_group("valuable input rate (VIR)")
    vir.add_argument(
        "--vir-numerator",
        default="new inputs",
        metavar="METRIC",
        help=advanced_help("ratio numerator; used when --plot-types includes vir"),
    )
    vir.add_argument(
        "--vir-denominator",
        default="exec total",
        metavar="METRIC",
        help=advanced_help("ratio denominator; used when --plot-types includes vir"),
    )
    vir.add_argument(
        "--vir-coverage-step",
        type=float,
        default=None,
        metavar="PCS",
        help=advanced_help(
            "fixed coverage step; used with vir; conflicts with --vir-points"
        ),
    )
    vir.add_argument(
        "--vir-points",
        type=int,
        default=31,
        metavar="N",
        help=advanced_help(
            "approximate milestones; used with vir; conflicts with "
            "--vir-coverage-step"
        ),
    )
    appearance = plot_parser.add_argument_group("figure appearance")
    appearance.add_argument(
        "-T", "--title", help="optional figure title; omitted by default"
    )
    appearance.add_argument(
        "--style",
        choices=tuple(STYLE_PRESETS),
        default="paper",
        help="coherent size and typography preset",
    )
    appearance.add_argument(
        "--error-band",
        choices=("none", "sd", "minmax"),
        default="none",
        help="repeat uncertainty; useful when --repeats > 1",
    )
    appearance.add_argument(
        "-D",
        "--debug",
        action="store_true",
        help=(
            "diagnostic time-series rendering: draw inferred tails dashed and "
            "add an extrapolation legend; requires --plot-types time"
        ),
    )
    appearance.add_argument(
        "--x-tick-intervals",
        type=int,
        default=12,
        metavar="N",
        help="equal x-axis intervals for time plots (N+1 ticks)",
    )
    appearance.add_argument(
        "--figure-size",
        nargs=2,
        type=float,
        metavar=("WIDTH", "HEIGHT"),
        help=advanced_help("figure size in inches; overrides --style dimensions"),
    )
    marker_toggle = appearance.add_mutually_exclusive_group()
    marker_toggle.add_argument(
        "--markers",
        dest="markers",
        action="store_true",
        default=None,
        help=advanced_help("show point markers; conflicts with --no-markers"),
    )
    marker_toggle.add_argument(
        "--no-markers",
        dest="markers",
        action="store_false",
        default=None,
        help=advanced_help("hide point markers; conflicts with --markers"),
    )
    grid_toggle = appearance.add_mutually_exclusive_group()
    grid_toggle.add_argument(
        "--grid",
        dest="grid",
        action="store_true",
        default=None,
        help=advanced_help("show the grid; conflicts with --no-grid"),
    )
    grid_toggle.add_argument(
        "--no-grid",
        dest="grid",
        action="store_false",
        default=None,
        help=advanced_help("hide the grid; conflicts with --grid"),
    )
    appearance.add_argument(
        "--legend-location",
        choices=(
            "best",
            "upper right",
            "upper left",
            "lower left",
            "lower right",
            "right",
            "center left",
            "center right",
            "lower center",
            "upper center",
            "center",
        ),
        default="best",
        help=advanced_help("legend placement"),
    )
    appearance.add_argument(
        "--legend-columns",
        type=int,
        default=0,
        metavar="N",
        help=advanced_help("legend columns; 0 automatically chooses up to three"),
    )
    plot_parser.epilog = """
Examples:
  bench_parser.py plot -b a{1..5}.log b{1..5}.log -a 5 -l A B \\
    -t 24h -i 1h -k coverage corpus --plot-types time -o plots

  bench_parser.py plot -b logs/*.log -a 5 -l A B C \\
    --plot-types time vir --curve-completion repeat --error-band sd -o plots

Curve completion:
  none keeps a fixed-repeat mean and ends at the shortest run; repeat holds the
  last value; trend always fits an endpoint-continuous growth-rate continuation
  and never switches to another mode. auto compares repeat and trend by
  rolling-origin normalized RMSE (prediction RMSE divided by observed
  validation-window growth), averaged equally across repeats for each
  fuzzer/metric; candidates within 5% prefer repeat.
  Completion applies only when --plot-types includes time. Completed tails use
  the original solid line style by default; -D marks inferred portions with
  dashed lines for diagnosis.

Sampling semantics:
  Uptime is absolute and is never shifted to zero. Nearest-record matching and
  gap detection are inferred from each log's cadence; there are no manual
  start/end-delay thresholds. Curves are always drawn from the analytical
  origin (0,0); this does not rebase uptime or alter observed time-series CSVs.
"""
    if show_advanced:
        plot_parser.epilog += """

Advanced relationships:
  * VIR controls require --plot-types vir. --vir-coverage-step conflicts with
    --vir-points.
  * --figure-size overrides the selected --style dimensions.
  * -D/--debug requires --plot-types time and only changes diagnostic styling;
    it does not change sampled, completed, or exported data.
"""

    args = parser.parse_args(raw_argv)
    active_parser = stat_parser if args.command == "stat" else plot_parser

    def option_used(*names: str) -> bool:
        return any(
            token == name or token.startswith(f"{name}=")
            for token in raw_argv
            for name in names
        )

    def require_options(
        target_parser: argparse.ArgumentParser,
        options: Sequence[str],
        requirement: str,
    ) -> None:
        verb = "requires" if len(options) == 1 else "require"
        target_parser.error(f"{', '.join(options)} {verb} {requirement}")

    if args.repeats <= 0:
        active_parser.error("--repeats must be positive")
    if len(args.bench_file) % args.repeats:
        active_parser.error("number of bench files must be divisible by --repeats")
    group_count = len(args.bench_file) // args.repeats
    if args.labels is not None and len(args.labels) != group_count:
        active_parser.error(f"expected {group_count} labels, got {len(args.labels)}")
    if args.labels is not None and len(set(args.labels)) != len(args.labels):
        active_parser.error("--labels must be unique")
    if len(set(args.metrics)) != len(args.metrics):
        active_parser.error("--metrics must be unique")

    if args.command == "stat":
        return args

    if len(set(args.plot_types)) != len(args.plot_types):
        plot_parser.error("--plot-types must be unique")
    has_time = "time" in args.plot_types
    has_vir = "vir" in args.plot_types
    time_only_options = (
        "-i",
        "--interval",
        "-k",
        "--metrics",
        "--curve-completion",
        "--x-tick-intervals",
        "-D",
        "--debug",
    )
    used_time_only = [name for name in time_only_options if option_used(name)]
    if not has_time and used_time_only:
        require_options(plot_parser, used_time_only, "'--plot-types time'")

    vir_options = (
        "--vir-numerator",
        "--vir-denominator",
        "--vir-coverage-step",
        "--vir-points",
    )
    used_vir_options = [name for name in vir_options if option_used(name)]
    if not has_vir and used_vir_options:
        require_options(plot_parser, used_vir_options, "'--plot-types vir'")
    if option_used("--vir-coverage-step") and option_used("--vir-points"):
        plot_parser.error("--vir-coverage-step conflicts with --vir-points")
    if args.vir_points < 3:
        plot_parser.error("--vir-points must be at least 3")
    if args.vir_coverage_step is not None and args.vir_coverage_step <= 0:
        plot_parser.error("--vir-coverage-step must be positive")
    args.vir_coverage_step = (
        0.0 if args.vir_coverage_step is None else args.vir_coverage_step
    )
    if args.x_tick_intervals <= 0:
        plot_parser.error("--x-tick-intervals must be positive")
    if args.dpi <= 0:
        plot_parser.error("--dpi must be positive")
    if args.figure_size is not None and any(value <= 0 for value in args.figure_size):
        plot_parser.error("--figure-size values must be positive")
    if args.legend_columns < 0:
        plot_parser.error("--legend-columns cannot be negative")

    return args


def experiment_labels(args: argparse.Namespace) -> list[str]:
    return args.labels or [
        args.bench_file[index * args.repeats].stem
        for index in range(len(args.bench_file) // args.repeats)
    ]


def load_experiment(
    bench_files: Sequence[Path],
    labels: Sequence[str],
    repeats: int,
    targets: np.ndarray,
    extraction_metrics: Sequence[str],
    summary_metrics: Sequence[str],
    completion_mode: str = "none",
) -> ExperimentData:
    raw_records: list[list[dict[str, float]]] = []
    sampled_runs: list[RunSeries] = []
    for path in bench_files:
        records = read_bench_log(path)
        raw_records.append(records)
        series = resample_run(path, records, targets, extraction_metrics)
        sampled_runs.append(series)

    grouped_runs: list[tuple[str, Sequence[RunSeries]]] = []
    grouped_raw: list[tuple[str, Sequence[Sequence[dict[str, float]]]]] = []
    groups: list[GroupSeries] = []
    auto_selections: dict[str, dict[str, dict[str, Any]]] = {}
    for group_index, label in enumerate(labels):
        start = group_index * repeats
        stop = start + repeats
        runs = sampled_runs[start:stop]
        raw = raw_records[start:stop]
        metric_modes: dict[str, str] | None = None
        if completion_mode == "auto":
            decisions = select_auto_completion(runs, raw, extraction_metrics)
            auto_selections[label] = decisions
            metric_modes = {
                metric: str(decision["selected"])
                for metric, decision in decisions.items()
            }
        for run, records in zip(runs, raw):
            extend_run_tail(
                run,
                completion_mode,
                records,
                metric_modes,
            )
        grouped_runs.append((label, runs))
        grouped_raw.append((label, raw))
        groups.append(aggregate_group(label, runs, summary_metrics))
    return ExperimentData(
        raw_records=raw_records,
        sampled_runs=sampled_runs,
        grouped_runs=grouped_runs,
        grouped_raw=grouped_raw,
        groups=groups,
        auto_selections=auto_selections,
    )


def format_stat_number(value: float) -> str:
    if not np.isfinite(value):
        return "N/A"
    if math.isclose(value, round(value), abs_tol=1e-9):
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"


def print_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  ".join(text.ljust(widths[index]) for index, text in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(text.ljust(widths[index]) for index, text in enumerate(row)))


def print_stat_report(
    data: ExperimentData,
    time_labels: Sequence[str],
    metrics: Sequence[str],
    show_runs: bool,
) -> None:
    health_rows: list[list[str]] = []
    for label, raw_runs in data.grouped_raw:
        chunks = [len(run) for run in raw_runs]
        starts = [run[0]["uptime"] for run in raw_runs]
        ends = [run[-1]["uptime"] for run in raw_runs]
        cadences = [infer_sampling_window(run)[0] for run in raw_runs]
        health_rows.append(
            [
                label,
                str(len(raw_runs)),
                f"{min(chunks)}..{max(chunks)}",
                f"{min(starts):g}..{max(starts):g}",
                f"{min(ends):g}..{max(ends):g}",
                f"{min(cadences):g}..{max(cadences):g}",
            ]
        )

    print("Log health")
    print_table(
        ["fuzzer", "runs", "chunks", "first uptime(s)", "last uptime(s)", "cadence(s)"],
        health_rows,
    )

    summary_rows: list[list[str]] = []
    for target_index, time_label in enumerate(time_labels):
        for label, runs in data.grouped_runs:
            for metric in metrics:
                values = np.asarray(
                    [run.values[metric][target_index] for run in runs], dtype=float
                )
                finite = values[np.isfinite(values)]
                if finite.size:
                    mean = format_stat_number(float(np.mean(finite)))
                    std = format_stat_number(float(np.std(finite, ddof=0)))
                    minimum = format_stat_number(float(np.min(finite)))
                    maximum = format_stat_number(float(np.max(finite)))
                else:
                    mean = std = minimum = maximum = "N/A"
                summary_rows.append(
                    [
                        time_label,
                        label,
                        metric,
                        mean,
                        std,
                        minimum,
                        maximum,
                        f"{finite.size}/{len(runs)}",
                    ]
                )

    print("\nMetrics at requested uptimes")
    print(
        "Means use available observed repeats only; 'runs' shows "
        "contributors/expected. No curve completion is applied."
    )
    print_table(
        ["time", "fuzzer", "metric", "mean", "std", "min", "max", "runs"],
        summary_rows,
    )

    if not show_runs:
        return
    run_rows: list[list[str]] = []
    for target_index, time_label in enumerate(time_labels):
        for label, runs in data.grouped_runs:
            for run in runs:
                source = run.source_uptime[target_index]
                distance = (
                    run.nearest_distances[target_index]
                    if run.nearest_distances is not None
                    else math.nan
                )
                run_rows.append(
                    [
                        time_label,
                        label,
                        run.name,
                        format_stat_number(float(source)),
                        format_stat_number(float(distance)),
                        *[
                            format_stat_number(float(run.values[metric][target_index]))
                            for metric in metrics
                        ],
                    ]
                )
    print("\nPer-run selected records")
    print_table(
        ["time", "fuzzer", "run", "source uptime(s)", "distance(s)", *metrics],
        run_rows,
    )


def resolve_plot_style(args: argparse.Namespace) -> PlotStyle:
    preset = STYLE_PRESETS[args.style]
    return PlotStyle(
        figure_size=(
            tuple(args.figure_size)
            if args.figure_size is not None
            else preset.figure_size
        ),
        font_family=preset.font_family,
        font_weight=preset.font_weight,
        axis_font_size=preset.axis_font_size,
        tick_font_size=preset.tick_font_size,
        legend_font_size=preset.legend_font_size,
        title_font_size=preset.title_font_size,
        line_width=preset.line_width,
        marker_size=preset.marker_size,
        band_alpha=preset.band_alpha,
        grid=preset.grid if args.grid is None else args.grid,
        grid_alpha=preset.grid_alpha,
        markers=preset.markers if args.markers is None else args.markers,
        legend_location=args.legend_location,
        legend_columns=args.legend_columns,
    )


def run_stat(args: argparse.Namespace) -> int:
    try:
        target_values = [parse_duration(value) for value in args.times]
        if len(set(target_values)) != len(target_values):
            raise ValueError("--time values must identify distinct uptimes")
        targets = np.asarray(target_values, dtype=float)
        data = load_experiment(
            args.bench_file,
            experiment_labels(args),
            args.repeats,
            targets,
            args.metrics,
            args.metrics,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Parsed {len(args.bench_file)} runs as {len(data.groups)} fuzzer groups "
        f"x {args.repeats} repeats."
    )
    print_stat_report(data, args.times, args.metrics, args.show_runs)
    return 0


def build_plot_manifest(
    args: argparse.Namespace,
    data: ExperimentData,
    targets: np.ndarray,
    end_seconds: float,
    interval_seconds: float,
    style: PlotStyle,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "command": "plot",
        "title": args.title,
        "end_seconds": end_seconds,
        "interval_seconds": interval_seconds,
        "target_count": int(targets.size),
        "plot_types": args.plot_types,
        "curve_completion": args.curve_completion,
        "debug": args.debug,
        "trend_policy": {
            "source": "all raw snapshots",
            "model": "rolling-validated endpoint-anchored damped growth rate",
            "mode_switching": "none; zero-decay linear rate remains in trend family",
        },
        "auto_policy": {
            "candidates": ["repeat", "trend"],
            "score": "rolling-origin normalized RMSE",
            "normalization": (
                "fold RMSE divided by max(validation-window growth, "
                "5% full-history growth, 1)"
            ),
            "aggregation": "equal mean across repeats for each fuzzer and metric",
            "tie_break": "within 5% prefer repeat, then trend",
        },
        "auto_selections": data.auto_selections,
        "repeats": args.repeats,
        "metrics": args.metrics,
        "style_preset": args.style,
        "figure_style": {
            "figure_size": list(style.figure_size),
            "font_family": style.font_family,
            "font_weight": style.font_weight,
            "axis_font_size": style.axis_font_size,
            "tick_font_size": style.tick_font_size,
            "legend_font_size": style.legend_font_size,
            "title_font_size": style.title_font_size,
            "line_width": style.line_width,
            "marker_size": style.marker_size,
            "grid": style.grid,
            "markers": style.markers,
        },
        "groups": [],
    }
    for (label, runs), raw_runs in zip(data.grouped_runs, data.grouped_raw):
        _raw_label, records_by_run = raw_runs
        manifest_group = {"label": label, "runs": []}
        for run, records in zip(runs, records_by_run):
            distances = run.nearest_distances[np.isfinite(run.nearest_distances)]
            cadence, sampling_radius = infer_sampling_window(records)
            manifest_group["runs"].append(
                {
                    "path": str(run.path),
                    "record_count": len(records),
                    "first_uptime": records[0]["uptime"],
                    "last_uptime": records[-1]["uptime"],
                    "inferred_cadence": cadence,
                    "sampling_radius": sampling_radius,
                    "observed_targets": int(run.observed.sum()),
                    "extrapolated_targets": int(run.extrapolated.sum()),
                    "largest_selected_distance": (
                        float(np.max(distances)) if distances.size else None
                    ),
                    "extension_models": run.extension_models,
                }
            )
        manifest["groups"].append(manifest_group)
    return manifest


def run_plot(args: argparse.Namespace) -> int:
    has_time = "time" in args.plot_types
    has_vir = "vir" in args.plot_types
    try:
        end_seconds = parse_duration(args.time)
        interval_seconds = parse_duration(args.interval)
        targets = build_targets(end_seconds, interval_seconds)
        extraction_metrics: list[str] = list(args.metrics) if has_time else []
        if has_vir:
            for metric in ("coverage", args.vir_numerator, args.vir_denominator):
                if metric not in extraction_metrics:
                    extraction_metrics.append(metric)
        data = load_experiment(
            args.bench_file,
            experiment_labels(args),
            args.repeats,
            targets,
            extraction_metrics,
            args.metrics if has_time else (),
            args.curve_completion if has_time else "none",
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    style = resolve_plot_style(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    configure_style(style)
    prefix_source = args.filename_prefix or args.title or "syzkaller-bench"
    prefix = f"{slugify(prefix_source)}_{duration_slug(end_seconds)}"
    if has_time:
        prefix += f"_{slugify(args.curve_completion)}"
    written: list[Path] = []

    if has_time:
        for metric in args.metrics:
            figure = plot_metric(
                data.groups,
                metric,
                end_seconds / 3_600.0,
                args.x_tick_intervals,
                args.title,
                args.error_band,
                style,
                args.debug,
            )
            written.extend(
                save_figure(
                    figure,
                    args.out_dir / f"{prefix}_{slugify(metric)}",
                    args.formats,
                    args.dpi,
                )
            )
        run_csv = args.out_dir / f"{prefix}_run_samples.csv"
        group_csv = args.out_dir / f"{prefix}_group_summary.csv"
        write_run_samples_csv(run_csv, data.grouped_runs, extraction_metrics)
        write_group_csv(group_csv, data.groups, args.metrics)
        written.extend([run_csv, group_csv])

    if has_vir:
        try:
            if args.vir_coverage_step > 0:
                coverage_step = args.vir_coverage_step
            else:
                maxima = []
                for _label, runs in data.grouped_raw:
                    for run in runs:
                        coverage, _vir = raw_vir_curve(
                            run, end_seconds, args.vir_numerator, args.vir_denominator
                        )
                        maxima.append(float(coverage[-1]))
                coverage_step = nice_step(max(maxima) / (args.vir_points - 1))
            vir_groups = [
                aggregate_vir_group(
                    label,
                    runs,
                    end_seconds,
                    args.vir_numerator,
                    args.vir_denominator,
                    coverage_step,
                )
                for label, runs in data.grouped_raw
            ]
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        vir_csv = args.out_dir / f"{prefix}_vir_over_coverage.csv"
        write_vir_csv(vir_csv, vir_groups)
        written.append(vir_csv)
        vir_figure = plot_vir(vir_groups, args.title, args.error_band, style)
        written.extend(
            save_figure(
                vir_figure,
                args.out_dir / f"{prefix}_vir_over_coverage",
                args.formats,
                args.dpi,
            )
        )

    manifest = build_plot_manifest(
        args, data, targets, end_seconds, interval_seconds, style
    )
    manifest_path = args.out_dir / f"{prefix}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    written.append(manifest_path)

    print(
        f"Parsed {len(args.bench_file)} runs as {len(data.groups)} fuzzer groups "
        f"x {args.repeats} repeats; generated {', '.join(args.plot_types)} plots."
    )
    print(
        f"Uptime sampling is cadence-aware and never rebased; "
        f"curve completion: {args.curve_completion if has_time else 'not applicable'}."
    )
    print(f"Wrote {len(written)} files to {args.out_dir}")
    for path in written:
        print(f"  {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "stat":
        return run_stat(args)
    return run_plot(args)


if __name__ == "__main__":
    raise SystemExit(main())
