"""
CalibrationTracker: tracks whether the agent's stated confidence scores
actually predict outcomes, and derives a discount factor when they don't.

Persists to a JSONL log so calibration history survives restarts —
an agent's track record shouldn't reset every time the process does.
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("OmegaCalibration")


class CalibrationTracker:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self._records: Dict[int, Dict[str, Any]] = {}
        self._next_idx = 0
        if os.path.exists(log_path):
            self._load_from_log()

    def _load_from_log(self):
        with open(self.log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry["type"] == "predict":
                    self._records[entry["idx"]] = {
                        "task_id": entry["task_id"],
                        "confidence": entry["confidence"],
                        "outcome": None,
                    }
                    self._next_idx = max(self._next_idx, entry["idx"] + 1)
                elif entry["type"] == "resolve":
                    if entry["idx"] in self._records:
                        self._records[entry["idx"]]["outcome"] = entry["outcome"]

    def _append_log(self, entry: Dict[str, Any]):
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def predict(self, task_id: str, confidence: float) -> int:
        """Record a stated confidence for a not-yet-resolved task. Returns an index to resolve() later."""
        idx = self._next_idx
        self._next_idx += 1
        self._records[idx] = {"task_id": task_id, "confidence": confidence, "outcome": None}
        self._append_log({"type": "predict", "idx": idx, "task_id": task_id, "confidence": confidence})
        return idx

    def resolve(self, idx: int, outcome: bool):
        """Record whether a previously predicted task actually succeeded."""
        if idx not in self._records:
            raise KeyError(f"No prediction with index {idx}")
        self._records[idx]["outcome"] = outcome
        self._append_log({"type": "resolve", "idx": idx, "outcome": outcome})

    def _resolved(self):
        return [r for r in self._records.values() if r["outcome"] is not None]

    def calibration_report(self) -> Dict[str, Any]:
        """
        Buckets resolved predictions by stated confidence (rounded to nearest 0.1)
        and honestly compares stated confidence against actual success rate per bucket.
        """
        resolved = self._resolved()
        buckets: Dict[str, list] = {}
        for r in resolved:
            key = f"{round(r['confidence'], 1)}"
            buckets.setdefault(key, []).append(r)

        bucket_stats = {}
        total_weighted_error = 0.0
        total_count = 0
        for key, items in buckets.items():
            stated_avg = sum(i["confidence"] for i in items) / len(items)
            actual_rate = sum(1 for i in items if i["outcome"]) / len(items)
            error = abs(stated_avg - actual_rate)
            bucket_stats[key] = {
                "stated_confidence_avg": round(stated_avg, 3),
                "actual_success_rate": round(actual_rate, 3),
                "calibration_error": round(error, 3),
                "count": len(items),
            }
            total_weighted_error += error * len(items)
            total_count += len(items)

        overall_error = round(total_weighted_error / total_count, 3) if total_count else 0.0

        return {
            "resolved_count": len(resolved),
            "overall_calibration_error": overall_error,
            "buckets": bucket_stats,
        }

    def suggested_discount(self) -> float:
        """
        Derives a multiplier to apply to future stated confidence values.
        Overconfident history (stated > actual) -> discount below 1.0.
        Well-calibrated or underconfident history -> stays near/above 1.0.
        Clamped to [0.1, 1.1] so one bad streak can't zero out the agent
        or let it inflate its own confidence beyond a small margin.
        """
        resolved = self._resolved()
        if not resolved:
            return 1.0
        stated_avg = sum(r["confidence"] for r in resolved) / len(resolved)
        actual_rate = sum(1 for r in resolved if r["outcome"]) / len(resolved)
        gap = stated_avg - actual_rate  # positive = overconfident
        discount = 1.0 - gap
        return round(max(0.1, min(1.1, discount)), 3)
