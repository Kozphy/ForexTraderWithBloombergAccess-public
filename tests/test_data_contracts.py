"""Phase 1 data-correctness and contract tests."""

import pandas as pd
import pytest

from forex_quant.data import (
    DataLineage,
    MissingDataPolicy,
    SURVIVORSHIP_BIAS_NOTES,
    assert_point_in_time,
    build_dataset,
    detect_duplicates,
    fingerprint_frame,
    normalize_timestamps,
    validate_golden_schema,
)
from forex_quant.pipeline import synthetic_fx_data


def test_timestamp_normalization_is_utc_aware():
    raw = pd.DataFrame(
        {
            "timestamp": ["2020-01-01 00:00:00", "2020-01-02 00:00:00"],
            "asset": ["EURUSD", "EURUSD"],
            "close": [1.1, 1.2],
        }
    )
    out = normalize_timestamps(raw)
    assert str(out["timestamp"].dt.tz) == "UTC"


def test_duplicate_detection():
    frame = synthetic_fx_data(periods=5)
    dup = pd.concat([frame.iloc[:1], frame.iloc[:1]], ignore_index=True)
    found = detect_duplicates(dup)
    assert len(found) == 2


def test_missing_reject_policy():
    frame = synthetic_fx_data(periods=10)
    frame.loc[0, "close"] = float("nan")
    lineage = DataLineage(source="test", dataset_version="t1", missing_policy=MissingDataPolicy.REJECT)
    with pytest.raises(ValueError, match="Missing close"):
        build_dataset(frame, lineage)


def test_schema_and_fingerprint_stable():
    frame = synthetic_fx_data(periods=30)
    lineage = DataLineage(source="synthetic", dataset_version="v1")
    bundle = build_dataset(frame, lineage)
    report = validate_golden_schema(bundle.frame)
    assert report.ok
    assert bundle.fingerprint == fingerprint_frame(bundle.frame)
    again = build_dataset(frame, lineage)
    assert again.fingerprint == bundle.fingerprint


def test_point_in_time_filter():
    frame = build_dataset(
        synthetic_fx_data(periods=20),
        DataLineage(source="synthetic", dataset_version="v1"),
    ).frame
    decision = frame["timestamp"].iloc[10]
    pit = assert_point_in_time(frame, decision)
    assert (pit["available_at"] <= decision).all()
    assert len(pit) < len(frame)


def test_survivorship_notes_present():
    assert "Survivorship bias" in SURVIVORSHIP_BIAS_NOTES
