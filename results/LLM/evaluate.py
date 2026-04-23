"""
분류 결과 평가.

사용법:
    uv run python results/LLM/evaluate.py                      # 모든 모델 요약
    uv run python results/LLM/evaluate.py --model qwen3-8b     # 특정 모델만
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from prompts import LABELS

OUTPUT_ROOT = SCRIPT_DIR / "output"


def load_predictions(jsonl: Path) -> list[dict]:
    return [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]


def compute_metrics(records: list[dict]) -> dict:
    total = len(records)
    correct = sum(1 for r in records if r["pred"] == r["true"])
    parse_fail = sum(1 for r in records if r["pred"] is None)
    errors = sum(1 for r in records if r.get("error"))

    per_class: dict[str, dict] = {}
    for label in LABELS:
        tp = sum(1 for r in records if r["true"] == label and r["pred"] == label)
        fp = sum(1 for r in records if r["true"] != label and r["pred"] == label)
        fn = sum(1 for r in records if r["true"] == label and r["pred"] != label)
        support = sum(1 for r in records if r["true"] == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    confusion: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        confusion[r["true"]][r["pred"] or "<none>"] += 1

    latencies = [r["latency_ms"] for r in records if r.get("latency_ms")]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "parse_fail": parse_fail,
        "errors": errors,
        "avg_latency_ms": avg_latency,
        "per_class": per_class,
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def print_report(name: str, metrics: dict, records: list[dict]) -> None:
    print(f"\n=== {name} ===")
    print(
        f"accuracy: {metrics['accuracy']:.3f} "
        f"({metrics['correct']}/{metrics['total']}) | "
        f"parse_fail: {metrics['parse_fail']} | errors: {metrics['errors']} | "
        f"avg_latency: {metrics['avg_latency_ms']:.0f}ms"
    )

    print("\nper-class:")
    print(f"  {'label':<8} {'P':>6} {'R':>6} {'F1':>6} {'support':>8}")
    for label in LABELS:
        m = metrics["per_class"][label]
        print(f"  {label:<8} {m['precision']:>6.3f} {m['recall']:>6.3f} {m['f1']:>6.3f} {m['support']:>8}")

    print("\nconfusion (rows=true, cols=pred):")
    header_labels = LABELS + ["<none>"]
    print(f"  {'':<10}" + "".join(f"{l:>8}" for l in header_labels))
    for true_label in LABELS:
        row = metrics["confusion"].get(true_label, {})
        print(f"  {true_label:<10}" + "".join(f"{row.get(c, 0):>8}" for c in header_labels))

    misclassified = [r for r in records if r["pred"] != r["true"]]
    if misclassified:
        print(f"\nmisclassified ({len(misclassified)}):")
        for r in misclassified[:20]:
            print(f"  {r['file']}  true={r['true']} pred={r['pred']}")
        if len(misclassified) > 20:
            print(f"  ... and {len(misclassified) - 20} more")


def evaluate_one(model_dir: Path) -> None:
    jsonl = model_dir / "predictions.jsonl"
    if not jsonl.exists():
        print(f"[skip] {model_dir.name} — no predictions.jsonl")
        return
    records = load_predictions(jsonl)
    metrics = compute_metrics(records)
    print_report(model_dir.name, metrics, records)
    (model_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Specific output dir name, or all if omitted")
    args = parser.parse_args()

    if args.model:
        evaluate_one(OUTPUT_ROOT / args.model)
    else:
        dirs = sorted(d for d in OUTPUT_ROOT.iterdir() if d.is_dir()) if OUTPUT_ROOT.exists() else []
        if not dirs:
            print(f"No results found under {OUTPUT_ROOT}")
            return
        for d in dirs:
            evaluate_one(d)


if __name__ == "__main__":
    main()
