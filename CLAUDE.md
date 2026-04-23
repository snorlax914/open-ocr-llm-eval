# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

open-ocr-llm-eval is an 8-week research project by Uncommon Lab to evaluate domain-specialized OCR and Small LLM models, then build a FastAPI-based MVP service. The pipeline processes document images through OCR extraction followed by LLM classification/summarization. Primary languages in docs and code comments are Korean and English.

## Development Environment

- **Python:** 3.12 (see `.python-version`)
- **Package manager:** uv
- **Virtual environment:** `.venv/`

### Setup & Dependency Commands

```bash
uv sync              # Install/sync all dependencies from pyproject.toml + uv.lock
uv add <package>     # Add a new dependency
uv run <script>      # Run a script within the virtual environment
```

### Running Model Test Scripts

```bash
uv run python results/OCR/GLM-OCR/test.py
uv run python results/OCR/PaddleOCR-VL/test.py
uv run python results/OCR/DeepSeek-OCR-2/test.py
```

## Architecture

```
Document Image → OCR Model → Extracted Text → LLM → Structured Output (JSON)
```

### Directory Layout

- `data/Sample/` — Test documents (source images + labeled ground truth)
- `docs/` — Weekly assignments, meeting notes, reports, evaluation metrics (`평가지표.md`)
- `results/OCR/` — OCR model test scripts and outputs (GLM-OCR, PaddleOCR-VL, DeepSeek-OCR-2)
- `results/LLM/` — LLM test scripts and outputs (EXAONE, Gemma, Qwen3.5)
- `scripts/` — Evaluation and consistency testing scripts (planned)
- `src/` — FastAPI backend service (planned)

### Model Stack

**OCR models** (ranked by OmniDocBench v1.5):
1. GLM-OCR (`zai-org/GLM-OCR`) — HuggingFace transformers, AutoProcessor/AutoModelForImageTextToText
2. PaddleOCR-VL-1.5 (`PaddlePaddle/PaddleOCR-VL-1.5`) — Multi-task (ocr, table, chart, formula, seal), bfloat16
3. DeepSeek-OCR-2 (`deepseek-ai/DeepSeek-OCR-2`) — Document-to-Markdown, custom `infer()` method

**LLM models:**
- Qwen3.5-4B (262K context, Apache 2.0)
- EXAONE 4.0-1.2B (Korean-specialized, NC license — research only)

### Evaluation Metrics

- **OCR:** CER/WER, TEDS (table structure), EMR (exact match), noise resistance
- **OCR+LLM:** ANLS (semantic similarity), human evaluation (Likert 1-5)
- **LLM:** LIE Score, LayoutRL Reward

## Git Conventions

Commit prefixes: `feat`, `fix`, `docs`, `research`, `experiment`, `test`, `chore`

Korean or English commit messages are both acceptable.

## Constraints

- GPU targets: Colab T4 (16GB) for basic testing, A100 (40GB) for larger models
- Korean-English bilingual document support required
- Instruct-tuned models preferred for structured JSON output
