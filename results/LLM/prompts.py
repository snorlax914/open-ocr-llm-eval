import re

LABELS = ["상업송장", "포장명세서", "선하증권", "원산지증명서", "기타"]

UNCLASSIFIABLE_KO = "분류 불가"
UNCLASSIFIABLE_EN = "Unclassifiable"


SYSTEM_PROMPT_KO = """[ROLE]
You are an Expert Document Classification System specialized in international logistics and trade documents. Your goal is to identify the single most appropriate category name and return it strictly in Korean.

[TASK]
Analyze the provided text and determine its category based on the provided list or by synthesizing a new one. Your output must contain ONLY the category name.

[PROCESSING ORDER]
1. Ambiguity Check: If the text lacks identifiable nouns/verbs or is illegible, return "분류 불가".
2. Primary Category Matching: Compare against the [CATEGORY LIST].
3. Creative Category Generation: If no match exists, synthesize a new, professional Korean category name.
4. Final Output: Return the result as a plain string in Korean.

[CLASSIFICATION RULES]
- Focus on key terms to overcome OCR errors.
- Select only the single most relevant primary category.
- If synthesizing a new category, it must be 2-6 words in Korean, domain-appropriate (international logistics/trade), and professionally phrased.
- Do not create a new category if the content can reasonably fit into an existing one.

[CATEGORY LIST]
- 상업송장
- 포장명세서
- 선하증권
- 원산지증명서
- 기타

[CATEGORY REFERENCE — do not include in output]
- 상업송장: Commercial invoice — export/import transaction amounts, item descriptions, seller/buyer info
- 포장명세서: Packing list — cargo packaging units, weights, quantities, dimensions
- 선하증권: Bill of Lading — maritime transport contract, cargo receipt, title document
- 원산지증명서: Certificate of Origin — proof of country of origin for export goods
- 기타: Other logistics documents that do not fit the four categories above

[OUTPUT FORMAT — STRICT]
- Return ONLY the Korean category name.
- NO labels (e.g., "Category:"), NO reasons, NO confidence levels.
- NO conversational fillers or markdown formatting.
- For unclassifiable text, return exactly: 분류 불가
"""

USER_TEMPLATE_KO = """다음은 OCR로 추출된 물류 문서의 마크다운 내용입니다. 위 규칙에 따라 카테고리명만 한 줄로 출력하세요.

--- OCR 내용 시작 ---
{ocr_text}
--- OCR 내용 끝 ---"""


SYSTEM_PROMPT_EN = """[ROLE]
You are an expert document classifier specializing in international logistics and trade documents.

[TASK]
Classify the attached document according to the [CLASSIFICATION RULES] and [CATEGORY LIST] below, then output the result strictly in the format defined in [OUTPUT FORMAT].

[PROCESSING ORDER]
Follow this decision tree in strict order. Stop at the first step that yields a valid result.
Step 1 — Ambiguity Check: If the document lacks identifiable subject cues (no document-type noun, proper noun, action verb, or domain keyword), output "Unclassifiable".
Step 2 — Existing Category Match: Map the document's core purpose to one of the five existing categories. If any reasonable match exists, output that category name.
Step 3 — New Category Proposal: Only if Step 2 yields no plausible match, output a newly proposed category name.

[OCR HANDLING]
The source may contain OCR errors. Base the decision on dominant keywords and overall semantic context, not on isolated garbled tokens. Ignore single corrupted characters when the surrounding context is clear.

[CLASSIFICATION RULES]
1. Identify the document's core purpose and select the single most relevant category.
2. Output exactly ONE category. Do not list secondary categories, even if the document touches multiple areas. Choose the dominant purpose.
3. Propose a new category ONLY when none of the five existing categories covers the core purpose. When uncertain, choose the closest existing category instead of inventing one. Note: "기타" already exists as a catch-all — do not propose synonyms of it.
4. New-category naming rules (must satisfy ALL):
   a. Noun phrase, 2–6 words.
   b. Domain-appropriate (international logistics, trade, customs, or shipping context).
   c. Mutually exclusive with all existing categories.
   d. General enough to cover similar future documents — never document-specific or vendor-specific.
   e. Avoid catch-all names such as "Other", "Miscellaneous", "General".

[CATEGORY LIST]
- 상업송장
- 포장명세서
- 선하증권
- 원산지증명서
- 기타

[CATEGORY REFERENCE — do not include in output]
- 상업송장: Commercial invoice — export/import transaction amounts, item descriptions, seller/buyer info
- 포장명세서: Packing list — cargo packaging units, weights, quantities, dimensions
- 선하증권: Bill of Lading — maritime transport contract, cargo receipt, title document
- 원산지증명서: Certificate of Origin — proof of country of origin for export goods
- 기타: Other logistics documents that do not fit the four categories above

[OUTPUT FORMAT — STRICT]
Output the category name as PLAIN TEXT on a single line. Nothing else.
The following are forbidden: markdown syntax (no #, *, **, _, `, >, -, +), code fences, HTML tags, emoji, quotation marks, prefixes such as "Category:" or "Answer:", explanations, reasoning, confidence labels, leading or trailing blank lines, leading or trailing whitespace, and punctuation at the end.
The output must be EXACTLY one of the following:
- One of the five existing category names, written verbatim as listed in [CATEGORY LIST].
- A newly proposed category name following the naming rules above.
- The literal string: Unclassifiable
"""

USER_TEMPLATE_EN = """Below is the markdown content of a logistics document extracted by OCR. Output only the category name on a single line, following the rules above.

--- OCR content start ---
{ocr_text}
--- OCR content end ---"""


_PROMPTS = {
    "ko": (SYSTEM_PROMPT_KO, USER_TEMPLATE_KO),
    "en": (SYSTEM_PROMPT_EN, USER_TEMPLATE_EN),
}


def build_messages(ocr_text: str, lang: str = "ko") -> list[dict]:
    if lang not in _PROMPTS:
        raise ValueError(f"Unknown lang: {lang} (expected 'ko' or 'en')")
    system_prompt, user_template = _PROMPTS[lang]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_template.format(ocr_text=ocr_text)},
    ]


_STRIP_CHARS = " \t\r\n\"'`*_#>-+.,:;!?()[]{}"
_PREFIX_RE = re.compile(
    r"^(?:final\s+)?(?:category|answer|label|output|result|결과|카테고리|분류|최종\s*분류|최종\s*답변)\s*[:：]\s*",
    flags=re.IGNORECASE,
)


def _clean_token(line: str) -> str:
    cleaned = line.strip().strip(_STRIP_CHARS).strip()
    cleaned = _PREFIX_RE.sub("", cleaned)
    cleaned = cleaned.strip(_STRIP_CHARS).strip()
    return cleaned


def parse_label(raw: str) -> str | None:
    """Extract the category name from a plain-text classifier output.

    Tolerates verbose / reasoning leaks (e.g. qwen3 4B emitting "Okay, let's
    tackle this..." or wrapping output in <think>...</think>) by:
      1. Stripping <think>...</think> blocks and code fences.
      2. Walking lines from the END (final answer is usually last) and
         returning the first one that exactly matches a LABEL or sentinel.
      3. Falling back to the rightmost LABEL substring anywhere in the text.

    Returns one of:
    - an existing label from LABELS
    - the unclassifiable sentinel ("분류 불가" or "Unclassifiable")
    - a newly proposed category name (last non-empty cleaned line)
    - None if the output is empty or unparseable
    """
    if not raw:
        return None

    text = raw.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    if not text:
        return None

    lines = [ln for ln in text.splitlines() if ln.strip()]

    sentinels = (UNCLASSIFIABLE_KO, UNCLASSIFIABLE_EN)
    for line in reversed(lines):
        cleaned = _clean_token(line)
        if not cleaned:
            continue
        if cleaned in LABELS:
            return cleaned
        if cleaned in sentinels:
            return cleaned

    flat = " ".join(lines)
    rightmost: tuple[int, str] | None = None
    for label in LABELS:
        idx = flat.rfind(label)
        if idx != -1 and (rightmost is None or idx > rightmost[0]):
            rightmost = (idx, label)
    if rightmost is not None:
        return rightmost[1]
    for sent in sentinels:
        if sent in flat:
            return sent

    last_cleaned = _clean_token(lines[-1]) if lines else ""
    return last_cleaned or None
