import re

LABELS = ["신고서", "신청서", "위임장", "확인서"]

SYSTEM_PROMPT_KO = """당신은 은행 문서를 4개 카테고리 중 하나로 분류하는 전문가입니다.

카테고리 정의:
- 신고서: 사건/사실/변경 내용을 은행에 알리기 위해 제출하는 문서 (예: 분실신고서, 변경신고서)
- 신청서: 특정 서비스/상품 가입이나 처리를 요청하는 문서 (예: 계좌개설신청서, 대출신청서)
- 위임장: 본인의 권한을 제3자에게 위임하는 문서
- 확인서: 특정 사실/상태를 증명하거나 확인하는 문서 (예: 잔액확인서, 거래확인서)

반드시 아래 JSON 형식으로만 응답하십시오. 다른 설명 금지.
{"label": "<카테고리명>"}
"""

USER_TEMPLATE_KO = """다음은 OCR로 추출된 은행 문서의 마크다운 내용입니다. 이 문서를 위 4개 카테고리 중 하나로 분류하세요.

--- OCR 내용 시작 ---
{ocr_text}
--- OCR 내용 끝 ---

JSON 형식으로만 응답: {{"label": "..."}}"""


SYSTEM_PROMPT_EN = """You are an expert that classifies Korean bank documents into one of 4 categories.

Category definitions:
- 신고서 (report/notice): A document submitted to notify the bank of an event, fact, or change (e.g. loss report, change-of-information notice).
- 신청서 (application): A document requesting enrollment in or processing of a specific service/product (e.g. account opening form, loan application).
- 위임장 (power of attorney): A document delegating the principal's authority to a third party.
- 확인서 (certificate/confirmation): A document proving or confirming a specific fact or status (e.g. balance certificate, transaction certificate).

Rules:
- Respond with the JSON object below and NOTHING ELSE. No explanation, no markdown fences.
- The value of "label" MUST be one of these exact Korean strings: 신고서, 신청서, 위임장, 확인서.

{"label": "<category>"}
"""

USER_TEMPLATE_EN = """Below is the markdown content of a Korean bank document extracted by OCR. Classify it into one of the 4 categories defined above.

--- OCR content start ---
{ocr_text}
--- OCR content end ---

Respond in JSON only: {{"label": "..."}}"""


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


def parse_label(raw: str) -> str | None:
    """Extract label from model output. Returns None if no valid label found."""
    match = re.search(r'\{[^{}]*"label"\s*:\s*"([^"]+)"[^{}]*\}', raw)
    if match:
        candidate = match.group(1).strip()
        if candidate in LABELS:
            return candidate

    for label in LABELS:
        if label in raw:
            return label
    return None
