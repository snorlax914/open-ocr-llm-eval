"""
분류 결과 평가.

[CATEGORY LIST]은 4종(상업송장·포장명세서·선하증권·원산지증명서)이고,
폴더 라벨은 5종(`기타` 포함)이다.

따라서:
- Core accuracy/F1: true ∈ 4 LABELS인 39장에서만 계산. pred는 4 LABELS / Unclassifiable / 새 카테고리 / <none> 중 하나로 집계.
- 기타 handling: true == 기타인 13장이 어떤 버킷으로 빠졌는지 분포만 본다 (모델이 `기타` LABEL을 모르기 때문에 정확도 개념이 성립하지 않음).
- New category proposals: 모델이 제안한 새 카테고리명을 카운트하여 명명 일관성을 확인.

사용법:
    uv run python results/LLM/evaluate.py                      # 모든 모델 요약
    uv run python results/LLM/evaluate.py --model qwen3-8b-ko  # 특정 모델만
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from prompts import LABELS, OTHER_LABEL, UNCLASSIFIABLE_EN, UNCLASSIFIABLE_KO

OUTPUT_ROOT = SCRIPT_DIR / "output"

UNC_BUCKET = "<unclassifiable>"
NEW_BUCKET = "<new_category>"
NONE_BUCKET = "<none>"

PRED_BUCKETS = LABELS + [UNC_BUCKET, NEW_BUCKET, NONE_BUCKET]


def load_predictions(jsonl: Path) -> list[dict]:
    return [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]


def bucket_pred(pred: str | None) -> str:
    if pred is None:
        return NONE_BUCKET
    if pred in LABELS:
        return pred
    if pred in (UNCLASSIFIABLE_KO, UNCLASSIFIABLE_EN):
        return UNC_BUCKET
    return NEW_BUCKET


def compute_metrics(records: list[dict]) -> dict:
    total = len(records)
    parse_fail = sum(1 for r in records if r["pred"] is None)
    errors = sum(1 for r in records if r.get("error"))

    core_records = [r for r in records if r["true"] in LABELS]
    core_total = len(core_records)
    core_correct = sum(1 for r in core_records if r["pred"] == r["true"])

    per_class: dict[str, dict] = {}
    for label in LABELS:
        tp = sum(1 for r in core_records if r["true"] == label and r["pred"] == label)
        fp = sum(1 for r in core_records if r["true"] != label and r["pred"] == label)
        fn = sum(1 for r in core_records if r["true"] == label and r["pred"] != label)
        support = sum(1 for r in core_records if r["true"] == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}

    confusion: dict[str, Counter] = defaultdict(Counter)
    for r in core_records:
        confusion[r["true"]][bucket_pred(r["pred"])] += 1

    other_records = [r for r in records if r["true"] == OTHER_LABEL]
    other_dist: Counter = Counter(bucket_pred(r["pred"]) for r in other_records)

    new_cat_counter: Counter = Counter()
    for r in records:
        if bucket_pred(r["pred"]) == NEW_BUCKET:
            new_cat_counter[r["pred"]] += 1

    latencies = [r["latency_ms"] for r in records if r.get("latency_ms")]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "total": total,
        "parse_fail": parse_fail,
        "errors": errors,
        "avg_latency_ms": avg_latency,
        "core_total": core_total,
        "core_correct": core_correct,
        "core_accuracy": core_correct / core_total if core_total else 0.0,
        "per_class": per_class,
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "other_total": len(other_records),
        "other_distribution": dict(other_dist),
        "new_categories": dict(new_cat_counter),
    }


def print_report(name: str, metrics: dict, records: list[dict]) -> None:
    print(f"\n=== {name} ===")
    print(
        f"total={metrics['total']} | "
        f"core_accuracy={metrics['core_accuracy']:.3f} "
        f"({metrics['core_correct']}/{metrics['core_total']}) | "
        f"parse_fail={metrics['parse_fail']} | errors={metrics['errors']} | "
        f"avg_latency={metrics['avg_latency_ms']:.0f}ms"
    )

    print("\nper-class (true ∈ 4 LABELS only):")
    print(f"  {'label':<12} {'P':>6} {'R':>6} {'F1':>6} {'support':>8}")
    for label in LABELS:
        m = metrics["per_class"][label]
        print(f"  {label:<12} {m['precision']:>6.3f} {m['recall']:>6.3f} {m['f1']:>6.3f} {m['support']:>8}")

    print("\nconfusion (rows=true, cols=pred-bucket):")
    print(f"  {'':<14}" + "".join(f"{c:>14}" for c in PRED_BUCKETS))
    for true_label in LABELS:
        row = metrics["confusion"].get(true_label, {})
        print(f"  {true_label:<14}" + "".join(f"{row.get(c, 0):>14}" for c in PRED_BUCKETS))

    other_dist = metrics["other_distribution"]
    other_total = metrics["other_total"]
    if other_total:
        print(f"\n기타 handling (true=기타, n={other_total}):")
        for bucket in PRED_BUCKETS:
            cnt = other_dist.get(bucket, 0)
            if cnt:
                pct = 100.0 * cnt / other_total
                print(f"  {bucket:<14} {cnt:>3}  ({pct:5.1f}%)")

    new_cats = metrics["new_categories"]
    if new_cats:
        print(f"\nnew categories proposed ({sum(new_cats.values())} predictions, {len(new_cats)} unique):")
        for name, cnt in sorted(new_cats.items(), key=lambda x: (-x[1], x[0])):
            print(f"  [{cnt:>2}x] {name}")

    misclassified = [r for r in records if r["true"] in LABELS and r["pred"] != r["true"]]
    if misclassified:
        print(f"\nmisclassified core ({len(misclassified)}):")
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
