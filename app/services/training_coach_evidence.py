"""Collect comparable, deduplicated experiment and fresh-validation evidence."""

import json
import math

import pandas as pd

from app.labels.future_return import FutureReturnLabel


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def object_json(value):
    try:
        result = json.loads(value or "{}")
        return clean(result) if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


def market_key(context):
    if not isinstance(context, dict):
        return None
    values = [context.get(key) for key in ("symbol", "timeframe", "data_source")]
    if not all(isinstance(value, str) and value for value in values):
        return None
    return tuple(value.upper() for value in values)


def collect_reports(models, parameters):
    expected = market_key(parameters)
    label_id = FutureReturnLabel(parameters["horizon_candles"], parameters["up_return_threshold"]).definition_id
    experiments, validations = {}, {}
    for model in models:
        metadata = object_json(model.metadata_json)
        events = metadata.get("review_history", [])
        for event in events if isinstance(events, list) else []:
            if not isinstance(event, dict) or event.get("type") not in ("controlled_experiment", "fresh_model_validation"):
                continue
            report = event.get("evidence")
            if not isinstance(report, dict) or market_key(report.get("market_context")) != expected or report.get("label_definition_id") != label_id:
                continue
            if (report.get("status") not in ("completed", "partial") or not report.get("evaluation_end")
                    or type(report.get("samples")) is not int or report["samples"] < 1
                    or not isinstance(report.get("results"), list)
                    or not all(isinstance(row, dict) for row in report["results"])):
                continue
            try:
                timestamp = pd.Timestamp(report["evaluation_end"])
                if pd.isna(timestamp) or timestamp.tzinfo is None:
                    continue
            except (ValueError, TypeError):
                continue
            target, key = (experiments, "experiment_id") if event["type"] == "controlled_experiment" else (validations, "validation_id")
            if isinstance(report.get(key), str):
                target[report[key]] = report
    sort = lambda reports: sorted(reports.values(), key=lambda report: pd.Timestamp(report["evaluation_end"]))
    return sort(experiments), sort(validations)


def fresh_boundary(report, history=None):
    value = report.get("outcome_end_time")
    if value:
        timestamp = pd.Timestamp(value)
    else:
        timestamp = pd.Timestamp(report["evaluation_end"])
        # Older reports saved feature time, not the final price used by its
        # label. Prefer original candle positions when available.
        horizon = report.get("purge_candles", 12)
        if history is not None and timestamp in history.index:
            position = history.index.get_loc(timestamp) + horizon
            if position < len(history):
                return history.index[position]
        minutes = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
        timestamp += pd.Timedelta(minutes=minutes[report["market_context"]["timeframe"].upper()] * horizon)
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError("recorded evaluation boundary is invalid")
    return timestamp


def persistence(experiment, validations):
    rows = []
    for row in experiment.get("results", []) if experiment else []:
        if row.get("status") != "completed":
            continue
        later = [result for report in validations if report.get("experiment_id") == experiment["experiment_id"]
                 for result in report.get("results", []) if result.get("status") == "completed" and result.get("model_id") == row["model_id"]]
        good = lambda scores: all(scores.get(direction, {}).get("beats_baseline") is True for direction in ("up", "down"))
        successes = sum(good(result.get("scores", {})) for result in later)
        rows.append({"model_id": row["model_id"], "recipe": row["recipe"], "initial_beats_baseline": good(row.get("scores", {})),
                     "fresh_periods": len(later), "fresh_periods_beating_baseline": successes,
                     "status": "not_yet_validated" if not later else "held_up" if successes == len(later) else "mixed_or_worse"})
    return rows
