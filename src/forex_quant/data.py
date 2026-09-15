"""Point-in-time market data layer with schema, lineage and fingerprinting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any

import pandas as pd


GOLDEN_SCHEMA = {
    "timestamp": "datetime64[ns, UTC]",
    "asset": "object",
    "close": "float64",
    "available_at": "datetime64[ns, UTC]",
}


class MissingDataPolicy(str, Enum):
    """How missing observations are treated before research use."""

    REJECT = "reject"
    FORWARD_FILL_LIMIT = "forward_fill_limit"
    DROP = "drop"


@dataclass(frozen=True)
class DataLineage:
    """Provenance record for a research dataset."""

    source: str
    dataset_version: str
    timezone: str = "UTC"
    point_in_time_required: bool = True
    missing_policy: MissingDataPolicy = MissingDataPolicy.REJECT
    notes: str = ""
    transformations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["missing_policy"] = self.missing_policy.value
        payload["transformations"] = list(self.transformations)
        return payload


@dataclass
class DatasetBundle:
    """Point-in-time dataset plus lineage and content fingerprint."""

    frame: pd.DataFrame
    lineage: DataLineage
    fingerprint: str
    schema_version: str = "fx_ohlc_v1"

    def metadata(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "lineage": self.lineage.to_dict(),
            "n_rows": int(len(self.frame)),
            "n_assets": int(self.frame["asset"].nunique()) if "asset" in self.frame else 0,
            "timestamp_min": str(self.frame["timestamp"].min()) if len(self.frame) else None,
            "timestamp_max": str(self.frame["timestamp"].max()) if len(self.frame) else None,
        }


@dataclass
class DataQualityReport:
    ok: bool
    issues: list[str] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.issues))


def normalize_timestamps(frame: pd.DataFrame, timezone: str = "UTC") -> pd.DataFrame:
    """Normalize timestamp columns to timezone-aware UTC (or configured zone)."""
    out = frame.copy()
    for col in ("timestamp", "available_at"):
        if col not in out.columns:
            continue
        series = pd.to_datetime(out[col], utc=True, errors="raise")
        if timezone.upper() != "UTC":
            series = series.dt.tz_convert(timezone)
        out[col] = series
    return out


def ensure_available_at(frame: pd.DataFrame) -> pd.DataFrame:
    """Default available_at to timestamp when not provided (same-bar availability)."""
    out = frame.copy()
    if "available_at" not in out.columns:
        out["available_at"] = out["timestamp"]
    return out


def detect_duplicates(frame: pd.DataFrame) -> pd.DataFrame:
    """Return duplicate (asset, timestamp) rows if any."""
    mask = frame.duplicated(subset=["timestamp", "asset"], keep=False)
    return frame.loc[mask].copy()


def apply_missing_policy(
    frame: pd.DataFrame,
    policy: MissingDataPolicy,
    *,
    forward_fill_limit: int = 1,
) -> pd.DataFrame:
    """Apply configured missing-data policy to close prices."""
    out = frame.sort_values(["asset", "timestamp"]).copy()
    if policy is MissingDataPolicy.REJECT:
        if out["close"].isna().any():
            raise ValueError("Missing close values violate REJECT policy")
        return out
    if policy is MissingDataPolicy.DROP:
        return out.dropna(subset=["close"]).reset_index(drop=True)
    if policy is MissingDataPolicy.FORWARD_FILL_LIMIT:
        out["close"] = out.groupby("asset", group_keys=False)["close"].ffill(limit=forward_fill_limit)
        if out["close"].isna().any():
            raise ValueError("Missing close values remain after forward-fill limit")
        return out
    raise ValueError(f"Unsupported missing policy: {policy}")


def validate_golden_schema(frame: pd.DataFrame) -> DataQualityReport:
    """Validate required columns and basic type/value invariants."""
    issues: list[str] = []
    required = {"timestamp", "asset", "close", "available_at"}
    missing = required.difference(frame.columns)
    if missing:
        issues.append(f"Missing columns: {sorted(missing)}")
        return DataQualityReport(ok=False, issues=issues)

    if not pd.api.types.is_datetime64_any_dtype(frame["timestamp"]):
        issues.append("timestamp must be datetime-like")
    if not pd.api.types.is_datetime64_any_dtype(frame["available_at"]):
        issues.append("available_at must be datetime-like")
    if frame["timestamp"].dt.tz is None:
        issues.append("timestamp must be timezone-aware")
    if frame["available_at"].dt.tz is None:
        issues.append("available_at must be timezone-aware")
    if frame[["timestamp", "asset"]].duplicated().any():
        issues.append("Duplicate asset/timestamp observations detected")
    if frame["close"].isna().any():
        issues.append("close contains nulls")
    if (frame["close"] <= 0).any():
        issues.append("close must be strictly positive")
    if (frame["available_at"] < frame["timestamp"]).any():
        issues.append("available_at earlier than timestamp violates causality")
    return DataQualityReport(ok=len(issues) == 0, issues=issues)


def assert_point_in_time(frame: pd.DataFrame, decision_time: pd.Timestamp) -> pd.DataFrame:
    """Return only rows whose available_at <= decision_time."""
    if decision_time.tzinfo is None:
        raise ValueError("decision_time must be timezone-aware")
    usable = frame.loc[frame["available_at"] <= decision_time].copy()
    return usable


def fingerprint_frame(frame: pd.DataFrame) -> str:
    """Stable SHA-256 fingerprint of sorted market observations."""
    ordered = frame.sort_values(["timestamp", "asset"]).reset_index(drop=True)
    payload = ordered.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_dataset(
    frame: pd.DataFrame,
    lineage: DataLineage,
    *,
    forward_fill_limit: int = 1,
) -> DatasetBundle:
    """Normalize, validate and fingerprint a point-in-time dataset."""
    out = ensure_available_at(frame)
    out = normalize_timestamps(out, timezone=lineage.timezone)
    out = apply_missing_policy(out, lineage.missing_policy, forward_fill_limit=forward_fill_limit)
    report = validate_golden_schema(out)
    report.raise_if_failed()
    fp = fingerprint_frame(out)
    return DatasetBundle(frame=out.reset_index(drop=True), lineage=lineage, fingerprint=fp)


# Survivorship-bias documentation (research contract, not executable data).
SURVIVORSHIP_BIAS_NOTES = """
Survivorship bias controls for FX research
==========================================

FX spot pairs do not "delist" like equities, but research universes still suffer
from selection effects:

1. Pair selection: including only currently liquid G10 pairs excludes historically
   traded crosses that later became illiquid or were abandoned by the desk.
2. Quote convention changes: pair inversions or convention switches can silently
   drop older series if not versioned.
3. Venue / liquidity filters: requiring a minimum ADV or tight spread at the end
   of the sample biases toward survivors of liquidity regimes.
4. Bloomberg ticker mapping: remapped or retired tickers must be joined via a
   point-in-time instrument master, never via today's ticker list alone.

Required practice in this repository:
- Record the instrument universe and membership rules in DataLineage.notes.
- Version the universe separately from price history (dataset_version).
- Prefer fixed historical membership for a study window rather than end-of-sample
  liquidity screens applied retrospectively.
- Document any pair added or removed mid-sample in experiment manifests.
"""
