# 감자빵 2주차 보고서 - 문서 카테고리 추천을 위한 LLM 탐색

본 프로젝트의 파이프라인(OCR → sLLM 카테고리 분류)에서  
OCR 결과 텍스트를 입력받아 문서 카테고리를 추천하는 Instruct LLM 후보를 조사하여 정리한다.

조사 기준일: 2026년 4월 23일

---

## 1. 선정 기준

| 기준 | 요구사항 |
|---|---|
| 모델 유형 | **Instruct(Non-thinking) 모델** — Thinking 없이 즉시 응답 |
| 응답 속도 | 서비스 기준 **5초 이내** (페이지당 전체 파이프라인 포함) |
| 태스크 | 문서 카테고리 분류 (사업자등록증, 인감증명서 등 단일 라벨 출력) |
| 다국어 | 한국어·영어 문서 모두 처리 가능 |
| 실행 환경 | RTX 3080 (12~16GB VRAM), Ollama 로컬 실행 + Colab 비교 |
| 출력 형식 | 카테고리명만 단답 출력 (불필요한 설명 최소화) |

### Instruct 모델을 사용해야 하는 이유

1. **속도**: Thinking 모델은 내부 추론 과정(`<think>...</think>`)이 추가되어 토큰 생성량이 2~5배 증가하고 응답 지연이 커짐. 카테고리 분류는 단순 분류 태스크로 복잡한 chain-of-thought가 불필요함.
2. **출력 제어**: Instruct 모델은 "카테고리명만 출력하라"는 지시를 잘 따름. Thinking 모델은 reasoning 과정을 억제해도 불필요한 설명이 포함되는 경우가 많음.
3. **비용 효율**: 동일 VRAM에서 Instruct 모델이 더 높은 throughput을 달성하여 동시 요청 처리에 유리.

---

## 2. LLM 후보 모델 목록

### 2.1. LLM 후보 (4개)

OCR을 통해 추출된 텍스트를 입력으로 받아 문서 카테고리를 분류하는 모델이다.  
카테고리 분류는 단답 출력의 단순 태스크이므로 **속도 > 정확도 > 출력 형식 준수** 순으로 우선순위를 두고 선정했다.

#### 1) Qwen3-8B Non-thinking (Alibaba) — Qwen2.5 후속 세대 성능 비교용

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Qwen3-8B | 8.2B (비임베딩 6.95B) | 2025년 5월 | 32K (YaRN 확장 128K) | Apache 2.0 |

- Thinking/Non-thinking 모드를 단일 모델 내에서 전환 가능 (`enable_thinking=False`)
- Non-thinking 모드에서 Qwen2.5-Instruct 수준의 빠른 응답 제공
- **100개 이상 언어** 지원, 한/중/일 아시아 언어 처리에서 동급 최강
- 공식 발표 기준 Qwen3-8B는 Qwen2.5-14B급 성능을 달성 (STEM, 코딩, 추론)
- Ollama에서 `ollama run qwen3:8b`로 즉시 실행 가능
- 카테고리 분류 시 Non-thinking 모드로 불필요한 reasoning 과정 없이 단답 출력 가능

> **버전 선택 근거**: Qwen3 Dense 모델은 0.6B, 1.7B, 4B, 8B, 14B, 32B의 6종으로 제공된다.
> 4B는 경량이나 1주차에서 Qwen3.5-4B로 이미 실험 예정이므로 중복.
> 14B 이상은 RTX 3080 VRAM(12GB)을 초과하여 양자화가 필수이고 속도 저하가 우려됨.
> 8B는 INT4 양자화 시 ~5GB VRAM으로 RTX 3080에서 여유 있게 구동되며,
> Non-thinking 모드에서 Qwen2.5-7B-Instruct 대비 성능 향상이 보고되어 직접 비교 가치가 높음.

**Ollama 실행**: `ollama run qwen3:8b` (INT4 기본 제공)  
**Colab 실행**: T4 환경 기준 INT4/INT8 양자화로 실험 가능

---

#### 2) Qwen2.5-7B-Instruct (Alibaba) — 과제 지정 모델

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Qwen2.5-7B-Instruct | 7B | 2024년 9월 | 128K | Apache 2.0 |

- 2주차 과제에서 **기존 검토 모델**로 명시된 후보
- 코딩·수학 벤치마크 동급 최상위 (MATH 75.5, HumanEval 84.8)
- **29개 이상 언어** 지원, 한국어 포함 다국어 처리 가능
- Ollama에서 가장 안정적인 커뮤니티 지원 및 검증 사례 보유
- 128K 컨텍스트로 긴 OCR 결과도 한 번에 입력 가능
- 단, 일반 세계지식(world knowledge)이 약하고 hallucination 이슈가 커뮤니티에서 보고됨 — 카테고리 분류는 지식보다 패턴 매칭에 가까우므로 영향 제한적

> **버전 선택 근거**: Qwen2.5 Instruct 모델은 0.5B, 1.5B, 3B, 7B, 14B, 32B, 72B로 제공된다.
> 3B 이하는 분류 정확도가 떨어질 우려가 있고, 14B 이상은 RTX 3080에서 FP16 구동 불가.
> 7B는 MMLU-Pro, IFEval 등에서 충분한 성능을 보이며 INT4 기준 ~4GB VRAM으로 구동 가능한 최적 지점.
> Qwen3-8B와의 세대 간 성능 차이를 직접 비교하는 기준점 역할.

**Ollama 실행**: `ollama run qwen2.5:7b-instruct`  
**Colab 실행**: T4 환경 기준 FP16/INT4 모두 가능

---

#### 3) Llama-3.1-8B-Instruct (Meta) — 동급 최고 속도, 비-Qwen 비교군

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Llama-3.1-8B-Instruct | 8B | 2024년 7월 | 128K | Llama 3.1 Community |

- Self-hosted LLM 리더보드 기준 **170 tokens/sec** 으로 동급 최고 속도
- 벤치마크: MMLU-Pro 48.3, IFEval 80.4, HumanEval 72.6
- 세계지식(world knowledge)이 Qwen2.5-7B 대비 우수하여 범용 안정성이 높음
- Qwen 계열 외 벤더 다양성을 확보하기 위한 비교군
- 한국어는 공식 지원 8개 언어(영/독/불/이/포/힌/스/태)에 **미포함**. 다만 학습 데이터에 한국어가 일부 포함되어 기본적인 처리는 가능하며, 커뮤니티 한국어 파인튜닝 모델(Bllossom 등)이 존재. Qwen 대비 한국어 문서 분류 정확도 차이 확인 필요

> **버전 선택 근거**: Llama 3.1 Instruct 모델은 8B, 70B, 405B로 제공된다.
> Llama 3.2는 텍스트 전용 모델이 1B/3B만 존재하고 8B급이 없으며, Llama 3.3은 70B만 제공되어 8B급은 3.1이 최신.
> 70B 이상은 RTX 3080 구동 불가. 8B는 FP16 ~16GB, INT4 ~5GB로 RTX 3080에서 구동 가능.
> 속도 벤치마크에서 170 tok/s를 기록해 응답 속도 5초 이내 요구사항에 가장 유리한 후보.

**Ollama 실행**: `ollama run llama3.1:8b`  
**Colab 실행**: T4 환경 기준 FP16/INT4 모두 가능

---

#### 4) Ministral-8B-Instruct-2410 (Mistral AI) — 과제 지정 모델

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Ministral-8B-Instruct-2410 | 8B | 2024년 10월 | 128K | Mistral Research License |

- 2주차 과제에서 **기존 검토 모델**로 명시된 후보 (Ministral3:8b)
- Mistral 계열의 8B급 Instruct 모델로 다양한 태스크에서 범용적 성능
- Mistral Research License로 연구용 무료, 상용 적용 시 별도 라이선스 필요
- Interleaved Sliding-Window Attention(128K/32K 교차) 아키텍처로 긴 문맥 효율적 처리
- Arena Hard 70.9로 Llama 3.1 8B(62.4) 대비 우위, HumanEval 76.8로 코드 태스크도 강점
- 다만 HuggingFace 커뮤니티 토론에서 Qwen2.5-7B 대비 전반적 벤치마크 열세가 보고됨
- 1주차에서 Ministral 3 3B를 이미 후보로 선정했으므로, Mistral 계열 8B급 성능을 확인하는 의미

> **버전 선택 근거**: 과제에서 직접 명시된 모델이므로 필수 포함.
> HuggingFace 토론(discussions/5)에서 "Looks like not as good as Qwen2.5 7B"라는 평가가 있으나,
> 카테고리 분류라는 특정 태스크에서의 실제 성능은 직접 테스트로 확인해야 함.
> 범용 벤치마크와 도메인 특화 태스크의 성능이 반드시 일치하지는 않기 때문.

**Ollama 실행**: `ollama run ministral:8b`  
**Colab 실행**: T4 환경 기준 INT4 양자화로 실험 가능

---

### 2.2. 최종 후보 비교 요약

| 기준 | Qwen3-8B (Non-thinking) | Qwen2.5-7B-Instruct | Llama-3.1-8B-Instruct | Ministral-8B-Instruct |
|---|---|---|---|---|
| 생성 속도 (Q4, RTX 3080급) | ~115 tok/s | ~90 tok/s (추정) | ~80 tok/s | 미측정 |
| MMLU-Pro | 미공개 (Qwen2.5-14B급) | 벤치마크 참조 | 48.3 | — |
| IFEval | 미공개 | 벤치마크 참조 | 80.4 | — |
| Arena Hard | — | — | 62.4 | 70.9 |
| 한국어 공식 지원 | ✅ 100개+ 언어 | ✅ 29개+ 언어 | ❌ 8개 언어 (한국어 미포함) | ⚠️ 10개 언어 |
| 라이선스 | Apache 2.0 | Apache 2.0 | Llama Community | Mistral Research |
| 선정 사유 | Qwen2.5 후속 세대 비교 | 과제 지정 모델 | 동급 최고 속도 | 과제 지정 모델 |

> 생성 속도는 RTX 3080 Ti Q4_K 4K 컨텍스트 기준 외부 벤치마크 참고치이며, 실험에서 동일 조건으로 실측 예정  
> 출처: [LocalScore.ai](https://www.localscore.ai), [Hardware-Corner](https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-3080-ti/)

---

## 3. 실험 구조

### 카테고리 분류 LLM (4개)

| 모델 | 선정 사유 | 속도 (Q4, 추정) |
|---|---|---|
| **Qwen3-8B (Non-thinking)** | Qwen2.5 후속 세대, 성능 향상 확인용 | ~115 tok/s |
| **Qwen2.5-7B-Instruct** | 과제 지정 모델, Qwen3와 세대 간 비교 기준점 | ~90 tok/s |
| **Llama-3.1-8B-Instruct** | 동급 최고 속도, Qwen 외 벤더 비교군 | ~80 tok/s |
| **Ministral-8B-Instruct-2410** | 과제 지정 모델, Mistral 계열 8B급 검증 | 미측정 |

```
OCR 추출 텍스트 → Instruct LLM → 카테고리명 단답 출력
대상: Qwen3-8B, Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct, Ministral-8B-Instruct
```

본 실험의 최종 출력 형식은 **카테고리명 단답**으로 설정한다.  
분류 태스크의 특성상 JSON이나 Markdown이 아닌 단일 카테고리명을 출력하도록 프롬프트를 설계하여  
후처리 파싱 없이 즉시 활용할 수 있도록 한다.

---

## 4. 실행 환경별 구동 가능 모델

| 환경 | VRAM | 정밀도 | 실행 가능 모델 |
|---|---|---|---|
| RTX 3080 (로컬/Ollama) | 12GB | INT4 (기본) | 4종 모두 구동 가능 |
| Colab 무료 (T4) | 16GB | INT4/INT8 | 4종 모두 구동 가능 |
| Colab 무료 (T4) | 16GB | FP16 | Qwen2.5-7B, Llama-3.1-8B (여유 있음) / Qwen3-8B, Ministral-8B (OOM 위험) |

> Ollama 기본 양자화(Q4_K_M 등)로 4종 모두 RTX 3080에서 구동 가능  
> 속도 비교는 동일 양자화 조건(INT4)에서 수행하여 공정성 확보

---

## 5. 평가 지표

| 지표 | 설명 |
|---|---|
| 카테고리 분류 정확도 | 정답 카테고리 대비 모델 출력 일치율 (Exact Match) |
| 응답 속도 | 입력→출력 완료까지 소요 시간 (ms), **5초 이내 여부** |
| 출력 형식 준수율 | 카테고리명만 출력하는지 vs 불필요한 설명이 포함되는 비율 |
| 한국어 문서 분류 정확도 | 한국어 문서에 대한 카테고리 분류 정확도 (영문 대비 비교) |
| 영문 문서 분류 정확도 | 영문 문서에 대한 카테고리 분류 정확도 |
| 한글/영문 프롬프트 성능 차이 | 동일 문서에 대해 한글 프롬프트 vs 영문 프롬프트의 정확도·속도 차이 |

---

## 6. 탈락 모델 및 사유

| 모델 | 탈락 사유 |
|---|---|
| Qwen3-14B / 32B | RTX 3080 VRAM(12GB) 초과, FP16 기준 28GB+ 필요 |
| Qwen3-4B | 1주차에서 Qwen3.5-4B로 이미 실험 예정, 중복 회피 |
| Qwen3-1.7B / 0.6B | 파라미터 부족으로 카테고리 분류 정확도 저하 우려 |
| Gemma-2-9B-it | FP16 ~18GB로 RTX 3080 OOM, Colab T4에서도 빡빡 |
| Phi-4-mini-instruct (3.8B) | 한국어 성능 미검증, 사실 지식 부족으로 문서 유형 판별에 불리 |
| SmolLM3-3B | 유럽어 중심 학습, 한국어 지원 약함 — 한국어 문서 분류 부적합 |
| Mistral-7B-Instruct-v0.3 | Ministral-8B이 후속 모델이므로 구세대 중복 |
| Mistral-Small-24B-Instruct | 24B급으로 RTX 3080 구동 불가 |
| DeepSeek-R1-Distill-Qwen-7B | Reasoning 특화 모델, Instruct(Non-thinking) 요구사항에 부적합 |
| EXAONE 4.0-1.2B | 1주차에서 한국어 기준점으로 이미 선정, 카테고리 분류 전용 비교군으로는 파라미터 부족 |

---

## 7. 리서치 참고 모델 (실험 대상 외)

아래 모델들은 성능은 우수하나 VRAM 제약 또는 태스크 부적합으로 실험 대상에서 제외하되 참고용으로 기록한다.

| 모델 | 파라미터 | 비고 |
|---|---|---|
| Qwen3.5-9B | 9B | MMLU-Pro 82.5, GPQA Diamond 81.7로 우수하나 bf16 ~18GB로 RTX 3080 초과 |
| Llama-3.1-70B-Instruct | 70B | 동급 최고 범용 성능, 로컬 구동 불가 |
| Mistral-Small-24B-Instruct | 24B | 다국어 강점, RTX 3080 구동 불가 |
| Gemma 4 E4B | 4.5B effective | 1주차 비교군으로 선정 완료, 카테고리 분류 실험은 8B급 중심으로 진행 |

---

## 8. 참고 자료

| 출처 | URL |
|---|---|
| Qwen3-8B 모델 카드 | https://huggingface.co/Qwen/Qwen3-8B |
| Qwen3 공식 블로그 | https://qwenlm.github.io/blog/qwen3/ |
| Qwen3-8B Ollama | https://ollama.com/library/qwen3:8b |
| Qwen2.5 공식 블로그 | https://qwenlm.github.io/blog/qwen2.5/ |
| Ministral-8B vs Qwen2.5 비교 토론 | https://huggingface.co/mistralai/Ministral-8B-Instruct-2410/discussions/5 |
| Self-Hosted LLM Leaderboard 2026 | https://onyx.app/self-hosted-llm-leaderboard |
| Best Open-Source SLMs 2026 | https://www.bentoml.com/blog/the-best-open-source-small-language-models |
| Best Open-Source LLM for Korean | https://www.siliconflow.com/articles/en/best-open-source-llm-for-korean |
| LLM Speed Benchmarks | https://www.inferless.com/learn/exploring-llms-speed-benchmarks-independent-analysis---part-3 |
| RTX 3080 Ti LLM 벤치마크 | https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-3080-ti/ |
| LocalScore.ai 모델별 속도 | https://www.localscore.ai/model/1 |
