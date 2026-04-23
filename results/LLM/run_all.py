"""
3개 모델 × 2개 언어 = 6개 조합 전체 실행.

모델 단위로 한 번 로딩 후 ko/en 연달아 돌려 로딩 비용 절감.
실패/중단 시 --skip-existing 으로 이어서 재개.

사용법:
    uv run python results/LLM/run_all.py
    uv run python results/LLM/run_all.py --skip-existing
    uv run python results/LLM/run_all.py --models qwen3 exaone    # 일부만
    uv run python results/LLM/run_all.py --langs ko               # 한국어만
    uv run python results/LLM/run_all.py --limit 4 --no-evaluate  # 스모크
"""

from __future__ import annotations

import argparse
import gc
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from classify import MODEL_CONFIG, run_classification


def free_runner(runner) -> None:
    """runner 메모리 해제. Ollama는 stop 호출, transformers는 파이썬 객체 삭제."""
    if runner is None:
        return

    if hasattr(runner, "unload"):
        runner.unload()
        return

    try:
        import torch

        if hasattr(runner, "model"):
            del runner.model
        if hasattr(runner, "tokenizer"):
            del runner.tokenizer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(MODEL_CONFIG.keys()),
                        choices=list(MODEL_CONFIG.keys()))
    parser.add_argument("--langs", nargs="+", default=["ko", "en"], choices=["ko", "en"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-evaluate", action="store_true", help="건너뛰기: 최종 evaluate.py 호출")
    args = parser.parse_args()

    total = len(args.models) * len(args.langs)
    print(f"=== running {total} combo(s): models={args.models} × langs={args.langs} ===\n")

    results: list[tuple[str, str, str, float]] = []  # (model, lang, status, secs)
    overall_start = time.perf_counter()

    for model_key in args.models:
        runner = None
        model_start = time.perf_counter()
        for lang in args.langs:
            combo_start = time.perf_counter()
            try:
                runner = run_classification(
                    model_key=model_key,
                    lang=lang,
                    limit=args.limit,
                    skip_existing=args.skip_existing,
                    runner=runner,
                )
                status = "ok"
            except Exception as e:
                print(f"[{model_key}/{lang}] FAILED: {e!r}")
                status = f"fail: {type(e).__name__}"
            elapsed = time.perf_counter() - combo_start
            results.append((model_key, lang, status, elapsed))

        free_runner(runner)
        runner = None
        print(f"\n--- {model_key} total: {time.perf_counter() - model_start:.1f}s ---\n")

    print("\n=== summary ===")
    for model_key, lang, status, secs in results:
        print(f"  {model_key:<10} {lang:<3} {status:<20} {secs:>7.1f}s")
    print(f"  total: {time.perf_counter() - overall_start:.1f}s")

    if not args.no_evaluate:
        print("\n=== evaluate ===")
        evaluate_script = SCRIPT_DIR / "evaluate.py"
        subprocess.run([sys.executable, str(evaluate_script)], check=False)


if __name__ == "__main__":
    main()
