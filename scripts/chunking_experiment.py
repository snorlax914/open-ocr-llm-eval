"""
마크다운 Chunking 전략 실험 스크립트 (과제 3 & 4)

과제 3: RecursiveCharacterTextSplitter / MarkdownHeaderTextSplitter / TokenTextSplitter / SemanticChunker 비교
과제 4: Overlap 비율(0/10/20/30%) × separator 정책(기본/테이블행) = 8조건 실험
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict

# ── Splitters ──
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    TokenTextSplitter,
)

# ── 경로 설정 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OCR_OUTPUT = PROJECT_ROOT / "results" / "OCR" / "paddleOCR-VL" / "output"

SAMPLES = {
    # ── 물류 (주 도메인) ──
    "[물류] 상업송장(소)": OCR_OUTPUT / "물류" / "1.상업송장" / "IMG_OCR_6_T_NV_000322" / "IMG_OCR_6_T_NV_000322.md",
    "[물류] 상업송장(대)": OCR_OUTPUT / "물류" / "1.상업송장" / "IMG_OCR_6_T_NV_001825" / "IMG_OCR_6_T_NV_001825.md",
    "[물류] 포장명세서": OCR_OUTPUT / "물류" / "2.포장명세서" / "IMG_OCR_6_T_PL_000554" / "IMG_OCR_6_T_PL_000554.md",
    "[물류] 선하증권(대)": OCR_OUTPUT / "물류" / "3.선하증권" / "IMG_OCR_6_T_BL_001677" / "IMG_OCR_6_T_BL_001677.md",
    "[물류] 원산지증명서": OCR_OUTPUT / "물류" / "4.원산지증명서" / "IMG_OCR_6_T_CO_001677" / "IMG_OCR_6_T_CO_001677.md",
    # ── 은행 (참고용) ──
    "[은행] 신청서": OCR_OUTPUT / "은행" / "신청서" / "IMG_OCR_6_F_0010603" / "IMG_OCR_6_F_0010603.md",
}

# ── 표 무결성 측정 ──

def count_table_tags(text: str) -> tuple[int, int]:
    """(open_count, close_count)"""
    opens = len(re.findall(r"<table[\s>]", text, re.IGNORECASE))
    closes = len(re.findall(r"</table>", text, re.IGNORECASE))
    return opens, closes


def table_integrity_score(chunks: list[str]) -> float:
    """청크별로 <table>과 </table> 쌍이 맞는 비율. 표가 없는 청크는 제외."""
    has_table = 0
    intact = 0
    for c in chunks:
        opens, closes = count_table_tags(c)
        if opens > 0 or closes > 0:
            has_table += 1
            if opens == closes:
                intact += 1
    return intact / has_table if has_table > 0 else 1.0


def estimate_tokens(text: str) -> int:
    """간이 토큰 추정: 영문 4자/토큰, 한글 1.5자/토큰 가중평균 대신 tiktoken 사용"""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 3


# ── 결과 구조체 ──

@dataclass
class SplitResult:
    splitter_name: str
    sample_name: str
    num_chunks: int = 0
    avg_chars: float = 0.0
    max_chars: int = 0
    avg_tokens: float = 0.0
    max_tokens: int = 0
    table_integrity: float = 0.0
    elapsed_sec: float = 0.0
    chunks_preview: list[str] = field(default_factory=list)  # 첫 100자씩


def evaluate_chunks(splitter_name: str, sample_name: str, chunks: list[str], elapsed: float) -> SplitResult:
    if not chunks:
        return SplitResult(splitter_name=splitter_name, sample_name=sample_name)

    char_lens = [len(c) for c in chunks]
    tok_lens = [estimate_tokens(c) for c in chunks]

    return SplitResult(
        splitter_name=splitter_name,
        sample_name=sample_name,
        num_chunks=len(chunks),
        avg_chars=round(sum(char_lens) / len(char_lens), 1),
        max_chars=max(char_lens),
        avg_tokens=round(sum(tok_lens) / len(tok_lens), 1),
        max_tokens=max(tok_lens),
        table_integrity=round(table_integrity_score(chunks), 3),
        elapsed_sec=round(elapsed, 4),
        chunks_preview=[c[:100] + "..." if len(c) > 100 else c for c in chunks[:3]],
    )


# ══════════════════════════════════════════════
# 과제 3: 4가지 Splitter 비교
# ══════════════════════════════════════════════

def run_recursive(text: str, chunk_size: int = 1500, overlap: int = 200,
                  separators: list[str] | None = None) -> list[str]:
    if separators is None:
        separators = ["\n## ", "\n### ", "\n\n", "\n", " ", ""]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=separators,
    )
    return splitter.split_text(text)


def run_markdown_header(text: str) -> list[str]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
    )
    docs = splitter.split_text(text)
    # 메타데이터를 청크 앞에 붙여서 반환
    results = []
    for doc in docs:
        meta_str = " > ".join(f"{k}: {v}" for k, v in doc.metadata.items()) if doc.metadata else ""
        prefix = f"[{meta_str}]\n" if meta_str else ""
        results.append(prefix + doc.page_content)
    return results


def run_token_splitter(text: str, chunk_size: int = 256, overlap: int = 50) -> list[str]:
    splitter = TokenTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
    )
    return splitter.split_text(text)


def run_semantic_chunker(text: str) -> list[str]:
    try:
        from langchain_experimental.text_splitter import SemanticChunker
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        try:
            from langchain_experimental.text_splitter import SemanticChunker
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except ImportError:
            print("  [SKIP] SemanticChunker: langchain_huggingface 또는 langchain_community 미설치")
            return []

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    splitter = SemanticChunker(embeddings)
    return splitter.split_text(text)


def run_hybrid(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """MarkdownHeader(1차) → Recursive(2차) 하이브리드"""
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
    )
    docs = md_splitter.split_text(text)

    rec_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    results = []
    for doc in docs:
        meta_str = " > ".join(f"{k}: {v}" for k, v in doc.metadata.items()) if doc.metadata else ""
        prefix = f"[{meta_str}]\n" if meta_str else ""
        sub_chunks = rec_splitter.split_text(doc.page_content)
        for sc in sub_chunks:
            results.append(prefix + sc)
    return results


def experiment_splitter_comparison():
    print("=" * 70)
    print("과제 3: 4가지 Splitter + 하이브리드 비교")
    print("=" * 70)

    splitters = {
        "RecursiveChar": lambda t: run_recursive(t),
        "MarkdownHeader": lambda t: run_markdown_header(t),
        "TokenSplitter": lambda t: run_token_splitter(t),
        "SemanticChunker": lambda t: run_semantic_chunker(t),
        "Hybrid(MdHeader→Recursive)": lambda t: run_hybrid(t),
    }

    all_results: list[SplitResult] = []

    for sample_name, sample_path in SAMPLES.items():
        text = sample_path.read_text(encoding="utf-8", errors="ignore").strip()
        print(f"\n{'─' * 50}")
        print(f"샘플: {sample_name} ({len(text)}자, ~{estimate_tokens(text)}토큰)")
        print(f"{'─' * 50}")

        for sp_name, sp_fn in splitters.items():
            t0 = time.perf_counter()
            chunks = sp_fn(text)
            elapsed = time.perf_counter() - t0

            result = evaluate_chunks(sp_name, sample_name, chunks, elapsed)
            all_results.append(result)

            print(f"\n  [{sp_name}]")
            print(f"    청크 수: {result.num_chunks}")
            print(f"    평균 길이: {result.avg_chars}자 / {result.avg_tokens}tok")
            print(f"    최대 길이: {result.max_chars}자 / {result.max_tokens}tok")
            print(f"    표 무결성: {result.table_integrity:.1%}")
            print(f"    소요 시간: {result.elapsed_sec:.4f}s")

    return all_results


# ══════════════════════════════════════════════
# 과제 4: Overlap 전략 탐색
# ══════════════════════════════════════════════

DEFAULT_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", " ", ""]
TABLE_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n|", "\n", " ", ""]  # \n| 추가


def count_broken_tables(chunks: list[str]) -> int:
    """<table>은 있지만 </table>이 없는 청크 수"""
    broken = 0
    for c in chunks:
        opens, closes = count_table_tags(c)
        if opens > closes:
            broken += 1
    return broken


def table_header_duplication_rate(chunks: list[str], original_text: str) -> float:
    """표가 분할된 경우, 두 번째 청크에 표 시작 태그가 있는지 (헤더 복제 효과)"""
    split_points = 0
    recovered = 0

    for i in range(len(chunks) - 1):
        curr_opens, curr_closes = count_table_tags(chunks[i])
        # 현재 청크에서 표가 열리고 안 닫힌 경우 = 다음 청크로 이어짐
        if curr_opens > curr_closes:
            split_points += 1
            next_opens, _ = count_table_tags(chunks[i + 1])
            if next_opens > 0:
                recovered += 1

    return recovered / split_points if split_points > 0 else 1.0


KEYWORDS = ["INVOICE", "B/L", "BILL OF LADING", "PACKING", "Origin",
            "CONSIGNEE", "SHIPPER", "상업송장", "포장명세서", "선하증권", "원산지"]


def keyword_boundary_preservation(chunks: list[str], original_text: str) -> float:
    """원본에 존재하는 키워드가 최소 하나의 청크에 완전히 포함되는 비율"""
    present_keywords = [kw for kw in KEYWORDS if kw.lower() in original_text.lower()]
    if not present_keywords:
        return 1.0

    preserved = 0
    for kw in present_keywords:
        for c in chunks:
            if kw.lower() in c.lower():
                preserved += 1
                break

    return preserved / len(present_keywords)


@dataclass
class OverlapResult:
    condition: str
    sample_name: str
    overlap_pct: int
    separator_type: str
    num_chunks: int = 0
    total_tokens: int = 0
    token_cost_increase_pct: float = 0.0
    table_integrity: float = 0.0
    broken_tables: int = 0
    table_header_dup_rate: float = 0.0
    keyword_preservation: float = 0.0


def experiment_overlap_strategy():
    print("\n\n" + "=" * 70)
    print("과제 4: Overlap 전략 탐색 (8조건)")
    print("=" * 70)

    chunk_size = 1500
    conditions = []
    for overlap_pct in [0, 10, 20, 30]:
        overlap = int(chunk_size * overlap_pct / 100)
        conditions.append((f"A{overlap_pct//10+1}", overlap_pct, overlap, DEFAULT_SEPARATORS, "기본"))
        conditions.append((f"B{overlap_pct//10+1}", overlap_pct, overlap, TABLE_SEPARATORS, "\\n| 추가"))

    all_results: list[OverlapResult] = []

    for sample_name, sample_path in SAMPLES.items():
        text = sample_path.read_text(encoding="utf-8", errors="ignore").strip()
        print(f"\n{'─' * 50}")
        print(f"샘플: {sample_name} ({len(text)}자)")
        print(f"{'─' * 50}")

        # 1차: MarkdownHeader
        md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
        )
        md_docs = md_splitter.split_text(text)

        baseline_tokens = {}  # 0% overlap 기준 토큰 수 (separator별)

        for cond_name, overlap_pct, overlap, seps, sep_label in conditions:
            # 2차: Recursive with varying overlap
            rec_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                separators=seps,
            )

            chunks = []
            for doc in md_docs:
                sub_chunks = rec_splitter.split_text(doc.page_content)
                chunks.extend(sub_chunks)

            # 메트릭 계산
            total_tokens = sum(estimate_tokens(c) for c in chunks)

            baseline_key = sep_label
            if overlap_pct == 0:
                baseline_tokens[baseline_key] = total_tokens

            cost_increase = 0.0
            if baseline_key in baseline_tokens and baseline_tokens[baseline_key] > 0:
                cost_increase = round(
                    (total_tokens - baseline_tokens[baseline_key]) / baseline_tokens[baseline_key] * 100, 1
                )

            result = OverlapResult(
                condition=cond_name,
                sample_name=sample_name,
                overlap_pct=overlap_pct,
                separator_type=sep_label,
                num_chunks=len(chunks),
                total_tokens=total_tokens,
                token_cost_increase_pct=cost_increase,
                table_integrity=round(table_integrity_score(chunks), 3),
                broken_tables=count_broken_tables(chunks),
                table_header_dup_rate=round(table_header_duplication_rate(chunks, text), 3),
                keyword_preservation=round(keyword_boundary_preservation(chunks, text), 3),
            )
            all_results.append(result)

            print(f"\n  [{cond_name}] overlap={overlap_pct}% separator={sep_label}")
            print(f"    청크 수: {result.num_chunks} | 총 토큰: {result.total_tokens} (+{cost_increase}%)")
            print(f"    표 무결성: {result.table_integrity:.1%} | 깨진 표: {result.broken_tables}")
            print(f"    표 헤더 복제율: {result.table_header_dup_rate:.1%}")
            print(f"    키워드 보존율: {result.keyword_preservation:.1%}")

    # 추가: chunk_size=800 강제 분할 시나리오
    print(f"\n\n{'─' * 50}")
    print("추가 실험: chunk_size=800 (표 강제 분할 시나리오)")
    print(f"{'─' * 50}")

    small_chunk = 800
    for sample_name, sample_path in SAMPLES.items():
        text = sample_path.read_text(encoding="utf-8", errors="ignore").strip()
        md_docs = md_splitter.split_text(text)

        for overlap_pct, sep_label, seps in [
            (0, "기본", DEFAULT_SEPARATORS),
            (20, "기본", DEFAULT_SEPARATORS),
            (20, "\\n| 추가", TABLE_SEPARATORS),
        ]:
            overlap = int(small_chunk * overlap_pct / 100)
            rec = RecursiveCharacterTextSplitter(
                chunk_size=small_chunk, chunk_overlap=overlap, separators=seps,
            )
            chunks = []
            for doc in md_docs:
                chunks.extend(rec.split_text(doc.page_content))

            ti = table_integrity_score(chunks)
            bt = count_broken_tables(chunks)
            hdr = table_header_duplication_rate(chunks, text)

            print(f"  {sample_name} | overlap={overlap_pct}% sep={sep_label}")
            print(f"    청크={len(chunks)} 표무결성={ti:.1%} 깨진표={bt} 헤더복제={hdr:.1%}")

    return all_results


# ══════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════

def main():
    # 샘플 파일 존재 확인
    for name, path in SAMPLES.items():
        if not path.exists():
            print(f"[ERROR] 샘플 파일 없음: {name} -> {path}")
            return

    # 과제 3
    splitter_results = experiment_splitter_comparison()

    # 과제 4
    overlap_results = experiment_overlap_strategy()

    # JSON 저장
    output_path = PROJECT_ROOT / "results" / "LLM" / "chunking_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "splitter_comparison": [asdict(r) for r in splitter_results],
        "overlap_strategy": [asdict(r) for r in overlap_results],
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()
