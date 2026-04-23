"""
문서 분류 테스트 러너.

사용법:
    uv run python results/LLM/classify.py --model qwen3 --lang ko
    uv run python results/LLM/classify.py --model qwen3 --lang en
    uv run python results/LLM/classify.py --model exaone --lang ko
    uv run python results/LLM/classify.py --model ministral --lang en
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from prompts import LABELS, build_messages, parse_label

OCR_ROOT = REPO_ROOT / "results" / "OCR" / "paddleOCR-VL" / "output"
OUTPUT_ROOT = SCRIPT_DIR / "output"

MODEL_CONFIG = {
    "qwen3": {
        "backend": "ollama",
        "model_id": "qwen3:8b",
        "output_dir": "qwen3-8b",
    },
    "exaone": {
        "backend": "ollama",
        "model_id": "exaone3.5:7.8b",
        "output_dir": "exaone-3.5-7.8b",
    },
    "ministral": {
        "backend": "transformers",
        "model_id": "mistralai/Ministral-3-8B-Instruct-2512-BF16",
        "output_dir": "ministral-3-8b",
    },
}


def collect_samples() -> list[tuple[str, Path]]:
    """Return list of (true_label, markdown_path) for every OCR output file."""
    samples: list[tuple[str, Path]] = []
    for md_path in OCR_ROOT.rglob("*.md"):
        label = None
        for part in md_path.parts:
            if part in LABELS:
                label = part
                break
        if label is None:
            continue
        samples.append((label, md_path))
    return sorted(samples, key=lambda x: str(x[1]))


def load_ocr_text(md_path: Path, max_chars: int = 8000) -> str:
    text = md_path.read_text(encoding="utf-8", errors="ignore").strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    return text


class OllamaRunner:
    def __init__(self, model_id: str):
        import ollama

        self.client = ollama.Client()
        self.model_id = model_id
        try:
            self.client.show(model_id)
        except Exception:
            print(f"[ollama] pulling {model_id}...")
            self.client.pull(model_id)

    def __call__(self, messages: list[dict]) -> str:
        resp = self.client.chat(
            model=self.model_id,
            messages=messages,
            options={"temperature": 0.0, "num_predict": 64},
            format="json",
            think=False,
            keep_alive="30s",
        )
        return resp["message"]["content"]

    def unload(self) -> None:
        """Ollama 모델을 즉시 VRAM에서 내림."""
        try:
            self.client.generate(model=self.model_id, prompt="", keep_alive=0)
        except Exception as e:
            print(f"[ollama] unload warning: {e!r}")


class TransformersRunner:
    def __init__(self, model_id: str):
        import torch
        from transformers import (
            AutoModelForImageTextToText,
            AutoTokenizer,
            BitsAndBytesConfig,
        )

        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, fix_mistral_regex=True)
        except TypeError:
            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            quantization_config=quant_cfg,
            device_map={"": 0},
            dtype=torch.bfloat16,
        )
        self.model.eval()

    def __call__(self, messages: list[dict]) -> str:
        import torch

        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=64,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        gen = out[0, inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(gen, skip_special_tokens=True)


def get_runner(backend: str, model_id: str):
    if backend == "ollama":
        return OllamaRunner(model_id)
    if backend == "transformers":
        return TransformersRunner(model_id)
    raise ValueError(f"Unknown backend: {backend}")


def run_classification(
    model_key: str,
    lang: str,
    limit: int | None = None,
    skip_existing: bool = False,
    runner=None,
):
    """단일 (모델, 언어) 조합 실행. runner 전달 시 재사용."""
    cfg = MODEL_CONFIG[model_key]
    out_dir = OUTPUT_ROOT / f"{cfg['output_dir']}-{lang}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"

    if skip_existing and pred_path.exists() and pred_path.stat().st_size > 0:
        print(f"[{model_key}/{lang}] skip (exists): {pred_path}")
        return runner

    samples = collect_samples()
    if limit:
        samples = samples[:limit]
    print(f"[{model_key}/{lang}] {len(samples)} samples | backend={cfg['backend']} | model={cfg['model_id']}")

    if runner is None:
        print(f"[{model_key}/{lang}] loading model...")
        runner = get_runner(cfg["backend"], cfg["model_id"])
        print(f"[{model_key}/{lang}] warming up...")
        t0 = time.perf_counter()
        try:
            runner([{"role": "user", "content": "ping"}])
        except Exception as e:
            print(f"[{model_key}/{lang}] warmup warning: {e!r}")
        print(f"[{model_key}/{lang}] warmup done ({int((time.perf_counter() - t0) * 1000)}ms)")

    with pred_path.open("w", encoding="utf-8") as f:
        for idx, (true_label, md_path) in enumerate(samples, start=1):
            ocr_text = load_ocr_text(md_path)
            messages = build_messages(ocr_text, lang=lang)

            t0 = time.perf_counter()
            try:
                raw = runner(messages)
                err = None
            except Exception as e:
                raw = ""
                err = repr(e)
            latency_ms = int((time.perf_counter() - t0) * 1000)

            pred = parse_label(raw) if raw else None
            rel = md_path.relative_to(OCR_ROOT)
            record = {
                "file": str(rel).replace("\\", "/"),
                "true": true_label,
                "pred": pred,
                "raw": raw,
                "latency_ms": latency_ms,
                "error": err,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

            status = "OK " if pred == true_label else ("?? " if pred is None else "MIS")
            print(f"[{idx}/{len(samples)}] {status} true={true_label} pred={pred} ({latency_ms}ms) {rel}")

    print(f"[{model_key}/{lang}] done → {pred_path}")
    return runner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=list(MODEL_CONFIG.keys()))
    parser.add_argument("--lang", default="ko", choices=["ko", "en"], help="Prompt language")
    parser.add_argument("--limit", type=int, default=None, help="Limit sample count (for smoke tests)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if predictions.jsonl already exists")
    args = parser.parse_args()

    run_classification(
        model_key=args.model,
        lang=args.lang,
        limit=args.limit,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
