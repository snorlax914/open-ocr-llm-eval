"""
LLM 카테고리 분류 평가 스크립트

3개 모델 × 3개 프롬프트로 문서 카테고리 분류 성능을 측정한다.
측정 항목: 정확도, 속도, JSON 파싱 성공률, 일관성(5회 반복)

사전 준비:
  ollama pull qwen3:8b
  ollama pull exaone3.5
  ollama pull ministral:8b

실행:
  uv run python scripts/eval_llm.py
  uv run python scripts/eval_llm.py --models qwen3:8b exaone3.5
  uv run python scripts/eval_llm.py --consistency    # 일관성 테스트 포함
"""

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"

MODELS = [
    "qwen3:8b",
    "exaone3.5",
    "ministral:8b",
]

USER_CATEGORIES = "사업자등록증, 인감증명서, 주민등록등본, 근로계약서, 세금계산서"

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "test_samples.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "LLM"

# ──────────────────────────────────────────────
# 프롬프트
# ──────────────────────────────────────────────

PROMPTS = {
    "ko": """당신은 한국어 문서를 분류하는 전문가입니다. OCR로 추출된 문서 본문을 보고
문서의 카테고리를 판별합니다.

[사용자 정의 카테고리]
{user_categories}

[판별 규칙]
1. 문서가 위 카테고리 중 하나에 명확히 해당하면 해당 카테고리명을 그대로 사용합니다.
2. 어느 카테고리에도 해당하지 않으면, 문서 내용을 바탕으로
   3~10자 이내의 새로운 카테고리명을 제안합니다.
3. OCR 노이즈로 판별이 불가능하면 "판별불가"로 응답합니다.
4. OCR 결과이므로 띄어쓰기·오탈자가 있을 수 있음을 감안합니다.
5. 반드시 아래 JSON 형식으로만 응답하고, 다른 설명은 포함하지 않습니다.

[출력 형식]
{{"category": "사업자등록증", "is_new_category": false, "key_evidence": "사업자등록증 등록번호"}}

[문서 본문]
{ocr_text}""",
    "en": """You are a document classification expert for Korean documents.
Given OCR-extracted text, determine the document category.

[User-defined categories]
{user_categories}

[Rules]
1. If the document clearly matches one of the above categories,
   output that exact category name in Korean.
2. If it matches none, propose a new category name
   (3-10 Korean characters) based on the document content.
3. If OCR noise makes classification impossible, output "판별불가".
4. Note that OCR output may contain spacing errors or typos.
5. Respond ONLY in the JSON format below. No explanations outside JSON.

[Output format]
{{"category": "사업자등록증", "is_new_category": false, "key_evidence": "사업자등록증 등록번호"}}

[Document text]
{ocr_text}""",
    "hybrid": """You are a Korean document classifier. Follow the instructions strictly.

[User-defined categories (Korean)]
{user_categories}

[Instructions]
1. Read the OCR text below (in Korean).
2. If the document matches one of the user-defined categories,
   return that category name exactly as given.
3. If none match, propose a new Korean category name
   (3-10 Hangul characters) summarizing the document type.
4. If OCR is too noisy to classify, return "판별불가".
5. Output must be valid JSON only. No prose, no markdown fences.

[Output format]
{{"category": "사업자등록증", "is_new_category": false, "key_evidence": "사업자등록증 등록번호"}}

[OCR text]
{ocr_text}""",
}

# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────


@dataclass
class SingleResult:
    sample_id: str
    model: str
    prompt_type: str
    raw_output: str
    parsed: dict | None
    json_valid: bool
    category: str
    correct: bool
    latency_ms: float


@dataclass
class ModelReport:
    model: str
    prompt_type: str
    total: int = 0
    correct: int = 0
    json_success: int = 0
    latencies: list[float] = field(default_factory=list)
    consistency_scores: list[float] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def json_rate(self) -> float:
        return self.json_success / self.total if self.total else 0.0

    @property
    def latency_p50(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        return s[len(s) // 2]

    @property
    def latency_p95(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    @property
    def avg_consistency(self) -> float:
        return (
            sum(self.consistency_scores) / len(self.consistency_scores)
            if self.consistency_scores
            else 0.0
        )


# ──────────────────────────────────────────────
# Ollama 호출
# ──────────────────────────────────────────────


def call_ollama(model: str, prompt: str) -> tuple[str, float]:
    """Ollama API를 호출하고 (응답 텍스트, 소요시간 ms)를 반환한다."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 256,
        },
        "format": "json",
    }

    start = time.perf_counter()
    resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
    elapsed_ms = (time.perf_counter() - start) * 1000

    resp.raise_for_status()
    return resp.json()["response"], elapsed_ms


# ──────────────────────────────────────────────
# 파싱 / 평가
# ──────────────────────────────────────────────


def parse_response(raw: str) -> dict | None:
    """LLM 출력에서 JSON을 추출한다."""
    text = raw.strip()

    # 마크다운 코드블록 제거
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue

    # 직접 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # { } 블록 추출
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def evaluate_single(
    sample: dict, model: str, prompt_type: str
) -> SingleResult:
    """단일 샘플에 대해 모델을 실행하고 결과를 반환한다."""
    prompt_template = PROMPTS[prompt_type]
    prompt = prompt_template.format(
        user_categories=USER_CATEGORIES,
        ocr_text=sample["ocr_text"],
    )

    raw_output, latency_ms = call_ollama(model, prompt)
    parsed = parse_response(raw_output)

    json_valid = parsed is not None
    category = parsed.get("category", "") if parsed else ""
    correct = category == sample.get("ground_truth", "")

    return SingleResult(
        sample_id=sample["id"],
        model=model,
        prompt_type=prompt_type,
        raw_output=raw_output,
        parsed=parsed,
        json_valid=json_valid,
        category=category,
        correct=correct,
        latency_ms=latency_ms,
    )


def check_consistency(
    sample: dict, model: str, prompt_type: str, repeats: int = 5
) -> float:
    """동일 입력을 repeats회 반복하여 일관성 비율을 반환한다."""
    results = []
    for _ in range(repeats):
        r = evaluate_single(sample, model, prompt_type)
        results.append(r.category)

    if not results:
        return 0.0
    most_common = max(set(results), key=results.count)
    return results.count(most_common) / len(results)


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────


def load_samples() -> list[dict]:
    """테스트 샘플을 로드한다."""
    if not DATA_PATH.exists():
        print(f"[!] 데이터 파일 없음: {DATA_PATH}")
        print("    data/test_samples.json에 테스트 데이터를 추가하세요.")
        return []

    with open(DATA_PATH, encoding="utf-8") as f:
        samples = json.load(f)

    if not samples:
        print("[!] 테스트 샘플이 비어 있습니다.")
        return []

    return samples


def run_evaluation(
    models: list[str],
    prompt_types: list[str],
    samples: list[dict],
    run_consistency: bool = False,
) -> list[ModelReport]:
    """전체 평가를 실행한다."""
    reports: list[ModelReport] = []

    for model in models:
        for pt in prompt_types:
            report = ModelReport(model=model, prompt_type=pt)
            print(f"\n{'='*60}")
            print(f"  모델: {model} | 프롬프트: {pt}")
            print(f"{'='*60}")

            for sample in samples:
                report.total += 1
                try:
                    result = evaluate_single(sample, model, pt)
                except Exception as e:
                    print(f"  [ERROR] {sample['id']}: {e}")
                    continue

                if result.json_valid:
                    report.json_success += 1
                if result.correct:
                    report.correct += 1
                report.latencies.append(result.latency_ms)

                status = "O" if result.correct else "X"
                print(
                    f"  [{status}] {sample['id']}: "
                    f"{result.category} ({result.latency_ms:.0f}ms)"
                )

                # 일관성 테스트
                if run_consistency:
                    score = check_consistency(sample, model, pt)
                    report.consistency_scores.append(score)
                    print(f"       일관성: {score:.0%}")

            reports.append(report)

    return reports


def print_summary(reports: list[ModelReport]) -> None:
    """결과 요약을 출력한다."""
    print(f"\n\n{'='*80}")
    print("  평가 결과 요약")
    print(f"{'='*80}\n")

    header = (
        f"{'모델':<25} {'프롬프트':<10} {'정확도':>8} "
        f"{'JSON':>8} {'p50(ms)':>10} {'p95(ms)':>10}"
    )
    has_consistency = any(r.consistency_scores for r in reports)
    if has_consistency:
        header += f" {'일관성':>8}"

    print(header)
    print("-" * len(header))

    for r in reports:
        line = (
            f"{r.model:<25} {r.prompt_type:<10} "
            f"{r.accuracy:>7.1%} {r.json_rate:>7.1%} "
            f"{r.latency_p50:>9.0f} {r.latency_p95:>9.0f}"
        )
        if has_consistency:
            line += f" {r.avg_consistency:>7.1%}"
        print(line)


def save_results(reports: list[ModelReport]) -> None:
    """결과를 JSON과 Markdown으로 저장한다."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    # JSON
    json_path = RESULTS_DIR / f"eval_{timestamp}.json"
    data = []
    for r in reports:
        data.append({
            "model": r.model,
            "prompt_type": r.prompt_type,
            "total": r.total,
            "accuracy": round(r.accuracy, 4),
            "json_parse_rate": round(r.json_rate, 4),
            "latency_p50_ms": round(r.latency_p50, 1),
            "latency_p95_ms": round(r.latency_p95, 1),
            "avg_consistency": round(r.avg_consistency, 4),
        })
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Markdown
    md_path = RESULTS_DIR / f"eval_{timestamp}.md"
    has_consistency = any(r.consistency_scores for r in reports)

    lines = [
        "# LLM 카테고리 분류 평가 결과\n",
        f"실행 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "",
    ]

    header = "| 모델 | 프롬프트 | 정확도 | JSON 파싱 | p50 (ms) | p95 (ms) |"
    sep = "|---|---|---|---|---|---|"
    if has_consistency:
        header += " 일관성 |"
        sep += "---|"

    lines.append(header)
    lines.append(sep)

    for r in reports:
        row = (
            f"| {r.model} | {r.prompt_type} | "
            f"{r.accuracy:.1%} | {r.json_rate:.1%} | "
            f"{r.latency_p50:.0f} | {r.latency_p95:.0f} |"
        )
        if has_consistency:
            row += f" {r.avg_consistency:.1%} |"
        lines.append(row)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n결과 저장: {json_path}")
    print(f"결과 저장: {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM 카테고리 분류 평가")
    parser.add_argument(
        "--models",
        nargs="+",
        default=MODELS,
        help="평가할 모델 목록 (기본: 4개 전체)",
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=["ko", "en", "hybrid"],
        choices=["ko", "en", "hybrid"],
        help="사용할 프롬프트 종류",
    )
    parser.add_argument(
        "--consistency",
        action="store_true",
        help="일관성 테스트 실행 (5회 반복, 느림)",
    )
    args = parser.parse_args()

    samples = load_samples()
    if not samples:
        return

    print(f"모델: {args.models}")
    print(f"프롬프트: {args.prompts}")
    print(f"샘플 수: {len(samples)}")
    print(f"일관성 테스트: {'ON' if args.consistency else 'OFF'}")

    reports = run_evaluation(
        models=args.models,
        prompt_types=args.prompts,
        samples=samples,
        run_consistency=args.consistency,
    )

    print_summary(reports)
    save_results(reports)


if __name__ == "__main__":
    main()
