# 문서 카테고리 추천 프롬프트

OCR 결과물을 기반으로 문서 카테고리를 분류·추천하기 위한 프롬프트 모음입니다.
한글 프롬프트(기본안), 영문 프롬프트(대조군), 하이브리드 프롬프트(멀티링구얼 모델용) 세 가지 버전을 제공합니다.

### 모델-프롬프트 매핑

| 프롬프트 | 권장 모델 |
|---|---|
| 한글 | EXAONE 3.5 7.8B |
| 영문 | Ministral-8B-Instruct |
| 하이브리드 | Qwen3-8B, Qwen2.5-7B-Instruct |

> 모든 모델에 3종 프롬프트를 모두 테스트하되, 위 매핑은 가장 잘 맞을 것으로 예상되는 조합이다.

---

## 1. 한글 프롬프트 (권장 기본안)

EXAONE 등 한국어 특화 모델에 권장합니다.

```
당신은 한국어 문서를 분류하는 전문가입니다. OCR로 추출된 문서 본문을 보고
문서의 카테고리를 판별합니다.

[사용자 정의 카테고리]
{user_categories}
예: 사업자등록증, 인감증명서, 주민등록등본, 근로계약서, 세금계산서

[판별 규칙]
1. 문서가 위 카테고리 중 하나에 명확히 해당하면 해당 카테고리명을 그대로 사용합니다.
2. 어느 카테고리에도 해당하지 않으면, 문서 내용을 바탕으로
   3~10자 이내의 새로운 카테고리명을 제안합니다.
3. OCR 노이즈로 판별이 불가능하면 "판별불가"로 응답합니다.
4. OCR 결과이므로 띄어쓰기·오탈자가 있을 수 있음을 감안합니다.
5. 반드시 아래 JSON 형식으로만 응답하고, 다른 설명은 포함하지 않습니다.

[출력 형식]
{"category": "사업자등록증", "is_new_category": false, "key_evidence": "사업자등록증 등록번호"}

[문서 본문]
{ocr_text}
```

---

## 2. 영문 프롬프트 (대조군)

성능 비교 및 A/B 테스트용 영문 버전입니다.

```
You are a document classification expert for Korean documents.
Given OCR-extracted text, determine the document category.

[User-defined categories]
{user_categories}
Examples: 사업자등록증 (Business Registration Certificate),
          인감증명서 (Seal Certificate),
          주민등록등본 (Resident Registration),
          근로계약서 (Employment Contract),
          세금계산서 (Tax Invoice)

[Rules]
1. If the document clearly matches one of the above categories,
   output that exact category name in Korean.
2. If it matches none, propose a new category name
   (3-10 Korean characters) based on the document content.
3. If OCR noise makes classification impossible, output "판별불가".
4. Note that OCR output may contain spacing errors or typos.
5. Respond ONLY in the JSON format below. No explanations outside JSON.

[Output format]
{"category": "사업자등록증", "is_new_category": false, "key_evidence": "사업자등록증 등록번호"}

[Document text]
{ocr_text}
```

---

## 3. 하이브리드 프롬프트 (멀티링구얼 모델 권장)

Qwen 등 멀티링구얼 베이스 모델에서 instruction following 정확도와
한국어 semantic 이해를 모두 챙기기 위한 버전입니다. 지시어는 영어, 카테고리·출력은 한국어.

```
You are a Korean document classifier. Follow the instructions strictly.

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
{"category": "사업자등록증", "is_new_category": false, "key_evidence": "사업자등록증 등록번호"}

[OCR text]
{ocr_text}
```

---

## 4. Few-shot 예시 (선택적 추가)

Zero-shot에서 새 카테고리 제안 시 명명 일관성이 부족하면
위 프롬프트의 규칙 섹션(`[판별 규칙]`, `[Rules]`, `[Instructions]`) 아래에
다음 예시 블록을 삽입합니다.

```
[예시]

예시 1)
입력: "입찰참가자격등록증... 등록번호 2024-... 발급일 ..."
출력: {"category": "입찰참가자격", "is_new_category": true, "key_evidence": "입찰참가자격등록증"}

예시 2)
입력: "사업자등록증 등록번호 123-45-67890 상호 ㈜..."
출력: {"category": "사업자등록증", "is_new_category": false, "key_evidence": "사업자등록증 등록번호"}

예시 3)
입력: "ㅁㄹㅁㄴㅇㄹ ##$ 2024 ㅁㄴㅇㄹ ... (심한 OCR 노이즈)"
출력: {"category": "판별불가", "is_new_category": false, "key_evidence": "OCR 노이즈로 판별 불가"}
```

---

## 5. 출력 형식 설계 근거

### confidence 필드를 제거한 이유

7-8B 모델은 자기 확신도를 정확하게 수치화하지 못한다.
confidence 0.95를 출력하더라도 실제 정확도와 상관관계가 약하여,
"confidence < 0.7이면 사람 검수"라는 정책이 실효성이 없다.
대신 `key_evidence` 필드로 판별 근거를 확인하고, 정확도가 낮은 케이스는
실험 결과의 Exact Match 실패 건을 수동 분석하여 패턴을 파악하는 방식이 현실적이다.

### 최종 출력 필드 (3개)

| 필드 | 타입 | 설명 |
|---|---|---|
| `category` | string | 카테고리명 (기존 카테고리 or 신규 제안 or "판별불가") |
| `is_new_category` | boolean | 기존 카테고리 매칭 여부 |
| `key_evidence` | string | 판별 근거 핵심 문구 (디버깅용, 40자 이내) |

---

## 6. 설계 포인트 체크리스트

프롬프트를 튜닝하거나 신규 카테고리에 맞게 변형할 때 확인할 사항입니다.

- **JSON 강제**: `"다른 설명은 포함하지 않습니다"` 문구가 없으면 7~8B 모델은
  "네, 분석해보겠습니다..." 같은 전문을 붙이는 경우가 많음.
  Ollama 사용 시 `format: "json"` 파라미터를 병행 권장.
- **출력 형식에 구체적 예시 사용**: `<true|false>`, `string`, `number` 같은
  타입 설명 대신 실제 값이 들어간 JSON 예시를 제공해야 소형 모델의 파싱 성공률이 높아짐.
- **Few-shot 2~3개**: zero-shot은 새 카테고리 명명 길이가 들쭉날쭉함.
  정규화된 예시를 넣으면 일관성이 크게 향상.
- **OCR 노이즈 명시**: 프롬프트에 OCR임을 알려야 오타 때문에
  잘못된 판별이 발생하는 빈도가 줄어듦.
- **카테고리명 길이 제한**: 3~10자 제약이 없으면 "~에 관한 증명서" 같은
  긴 카테고리명이 생성되어 UI 깨짐.
- **Temperature**: 분류 작업은 `temperature=0` 고정 권장.

---

## 7. A/B 테스트 평가 지표

세 가지 프롬프트 버전을 비교할 때 측정할 지표입니다.

| 지표 | 설명 | 목표 |
|------|------|------|
| Accuracy | 정답 카테고리 일치율 | ≥ 90% |
| JSON parse 성공률 | 유효한 JSON 출력 비율 | ≥ 99% |
| Consistency | 동일 입력 5회 반복 시 동일 출력 비율 (temp=0) | ≥ 95% |
| Latency p50 | 건당 응답 시간 중앙값 | 모델별 기준선 설정 |
| Latency p95 | 건당 응답 시간 95 percentile | p50의 2배 이내 |
| New category F1 | 새 카테고리 제안의 정밀도/재현율 | ≥ 0.80 |

평가셋 구성: 기존 카테고리당 20~30건 + "기존 카테고리 외" 50건 + OCR 노이즈 10건.

> 평가셋 데이터는 공공기관 문서, 학교 PDF, 비즈니스 문서 등에서 수집 예정.
> 수집 전까지는 `data/test_samples.json`에 소규모 파일럿 데이터로 프롬프트 동작을 검증한다.
