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
| 태스크 | 문서 카테고리 분류 (용선계약서, 사고보고서, 정산서, 근로계약서 등 단일 라벨 출력) |
| 대상 도메인 | 물류 — 상사계약, 운영·관리, 보험·사고, 재무, 일반 행정·HR 등 |
| 다국어 | 한국어·영어 혼용 문서 처리 가능 (물류 문서는 한영 혼용이 빈번) |
| 실행 환경 | RTX 3080 (12~16GB VRAM), Ollama 로컬 실행 + Colab 비교 |
| 출력 형식 | 카테고리명만 단답 출력 (불필요한 설명 최소화) |

### Instruct 모델을 사용해야 하는 이유

1. **속도**: Thinking 모델은 내부 추론 과정(`<think>...</think>`)이 추가되어 토큰 생성량이 2~5배 증가하고 응답 지연이 커짐. 카테고리 분류는 단순 분류 태스크로 복잡한 chain-of-thought가 불필요함.
2. **출력 제어**: Instruct 모델은 "카테고리명만 출력하라"는 지시를 잘 따름. Thinking 모델은 reasoning 과정을 억제해도 불필요한 설명이 포함되는 경우가 많음.
3. **비용 효율**: 동일 VRAM에서 Instruct 모델이 더 높은 throughput을 달성하여 동시 요청 처리에 유리.

---

## 2. LLM 후보 모델 목록

### 2.1. 최종 후보 (3개)

OCR을 통해 추출된 물류 도메인 문서 텍스트를 입력받아 카테고리를 분류하는 모델이다.  
물류 문서는 계약서·정산서 등 한국어 본문에 영문 해운 용어(NYPE, B/L, CII 등)가 혼용되는 특성이 있으므로 한영 이중언어 처리 능력이 중요하다.  
카테고리 분류는 단답 출력의 단순 태스크이므로 **속도 > 정확도 > 출력 형식 준수** 순으로 우선순위를 두고 선정했다.

#### 1) Qwen3-8B Non-thinking (Alibaba)

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Qwen3-8B | 8.2B (비임베딩 6.95B) | 2025년 5월 | 32K (YaRN 확장 128K) | Apache 2.0 |

- Thinking/Non-thinking 모드를 단일 모델 내에서 전환 가능 (`enable_thinking=False`)
- Non-thinking 모드에서 Qwen2.5-Instruct 수준의 빠른 응답 제공
- **100개 이상 언어** 지원, 한/중/일 아시아 언어 처리에서 동급 최강
- 공식 발표 기준 Qwen3-8B는 Qwen2.5-14B급 성능을 달성 (STEM, 코딩, 추론)
- Ollama에서 `ollama run qwen3:8b`로 즉시 실행 가능
- 카테고리 분류 시 Non-thinking 모드로 불필요한 reasoning 과정 없이 단답 출력 가능

> **선정 근거**: Qwen3 Dense 모델은 0.6B, 1.7B, 4B, 8B, 14B, 32B의 6종으로 제공된다.
> 4B는 1주차에서 Qwen3.5-4B로 이미 실험 예정이므로 중복, 14B 이상은 RTX 3080 VRAM 초과.
> 8B는 INT4 양자화 시 ~5GB VRAM으로 RTX 3080에서 여유 있게 구동된다.
>
> 같은 Qwen 계열인 **Qwen2.5-7B-Instruct**도 검토했으나,
> Qwen3-8B가 동일 계열 상위호환(학습 데이터 36T vs 18T, 119개 언어 vs 29개, Qwen2.5-14B급 성능)이므로
> 두 모델을 동시에 넣는 것은 슬롯 낭비로 판단하여 Qwen3-8B만 채택했다.

**Ollama 실행**: `ollama run qwen3:8b` (INT4 기본 제공)  
**Colab 실행**: T4 환경 기준 INT4/INT8 양자화로 실험 가능

---

#### 2) EXAONE 3.5 7.8B Instruct (LG AI Research)

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| EXAONE-3.5-7.8B-Instruct | 7.8B (비임베딩 6.98B) | 2024년 12월 | 32K | EXAONE AI Model License 1.1 - NC |

- LG AI Research에서 개발한 **한국어·영어 이중언어 특화** 모델
- 한국어 벤치마크: **KoMT-Bench 7.96**, **LogicKor 9.08**로 동급 최고 수준
- 범용 벤치마크: Arena Hard 68.7, IFEval 78.9, MT-Bench 8.29
- 물류 관련 한국어 문서(용선계약서, 정산서, 사고보고서 등)의 문맥 파악에 한영 이중언어 학습이 유리할 것으로 기대
- Ollama에서 `ollama run exaone3.5`로 즉시 실행 가능 (4.8GB, Q4 기본)
- **NC 라이선스**로 연구/비상용 목적 무료, 상용 적용 시 LG AI Research 별도 협의 필요

> **선정 근거**: EXAONE 시리즈는 3.5(2.4B/7.8B/32B)와 4.0(1.2B/32B)이 있다.
> EXAONE 4.0은 7-8B급 모델이 없어 선택 불가, 3.5 2.4B는 파라미터 부족, 32B는 RTX 3080 구동 불가.
> 7.8B는 INT4 양자화 시 ~5GB VRAM으로 RTX 3080에서 여유 있게 구동되며,
> 한국어 문서 분류에 가장 적합한 크기·성능 조합이다.
>
> 과제에서 제안된 **HyperCLOVA X SEED 8B**도 검토했으나,
> HuggingFace 확인 결과 텍스트 전용 Instruct 8B 모델이 존재하지 않았다
> (Omni-8B은 멀티모달, Text-Instruct는 0.5B/1.5B만 존재).
> 한국어 특화 8B급 텍스트 전용 모델로는 EXAONE 3.5 7.8B가 유일한 선택지이다.

**Ollama 실행**: `ollama run exaone3.5` (Q4 기본 제공, 4.8GB)  
**Colab 실행**: T4 환경 기준 FP16/INT4 모두 가능

---

#### 3) Ministral-8B-Instruct-2410 (Mistral AI)

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Ministral-8B-Instruct-2410 | 8B | 2024년 10월 | 128K | Mistral Research License |

- 과제에서 도입 검토 모델로 명시된 후보 (Ministral3:8b)
- Interleaved Sliding-Window Attention(128K/32K 교차) 아키텍처로 긴 문맥 효율적 처리
- Arena Hard 70.9, HumanEval 76.8, MT-Bench 8.3
- Mistral Research License로 연구용 무료, 상용 적용 시 별도 라이선스 필요
- HuggingFace 커뮤니티 토론에서 Qwen2.5-7B 대비 전반적 벤치마크 열세가 보고되었으나, 카테고리 분류 태스크에서의 실제 성능은 직접 테스트로 확인 필요

> **선정 근거**: 과제에서 도입 검토 모델로 명시(Ministral3:8b).
> HuggingFace 토론(discussions/5)에서 Qwen2.5-7B 대비 범용 벤치마크 열세가 보고되었고,
> 한국어 벤치마크(KoBALT)에서도 0.17로 낮은 점수를 기록하여 한국어 분류 성능에 우려가 있다.
> 그러나 카테고리 분류는 범용 벤치마크와 반드시 일치하지 않으므로 직접 테스트로 확인한다.
>
> 후속 모델인 **Ministral 3 8B (2512)**도 검토했으나,
> 비전 인코더(0.4B)가 포함된 멀티모달 모델이라 OCR 텍스트만 입력하는 분류 태스크에는
> 불필요한 오버헤드가 발생한다. 텍스트 전용인 2410 버전이 분류 태스크에 더 적합하다.

**Ollama 실행**: `ollama run ministral:8b`  
**Colab 실행**: T4 환경 기준 INT4 양자화로 실험 가능

---

### 2.2. 최종 후보 비교 요약

| 기준 | Qwen3-8B (Non-thinking) | EXAONE 3.5 7.8B | Ministral-8B-Instruct |
|---|---|---|---|
| 생성 속도 (Q4, RTX 3080급) | ~115 tok/s | 미측정 (동급 추정) | 미측정 |
| IFEval | 미공개 | 78.9 | — |
| Arena Hard | — | 68.7 | 70.9 |
| 한국어 벤치마크 | — | KoMT 7.96 / LogicKor 9.08 | KoBALT 0.17 |
| 한국어 공식 지원 | ✅ 100개+ 언어 | ✅ 한영 이중언어 특화 | ⚠️ 10개 언어 |
| 라이선스 | Apache 2.0 | ⚠️ NC (비상용) | Mistral Research |

> 생성 속도는 RTX 3080 Ti Q4_K 4K 컨텍스트 기준 외부 벤치마크 참고치이며, 실험에서 동일 조건으로 실측 예정  
> 출처: [LocalScore.ai](https://www.localscore.ai), [Hardware-Corner](https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-3080-ti/)

---

## 3. 실험 구조

### 카테고리 분류 LLM (3개)

| 모델 | 속도 (Q4, 추정) |
|---|---|
| **Qwen3-8B (Non-thinking)** | ~115 tok/s |
| **EXAONE 3.5 7.8B** | 미측정 (동급 추정) |
| **Ministral-8B-Instruct-2410** | 미측정 |

```
OCR 추출 텍스트 → Instruct LLM → 카테고리명 단답 출력
대상: Qwen3-8B, EXAONE-3.5-7.8B, Ministral-8B-Instruct
```

본 실험의 최종 출력 형식은 **카테고리명 단답**으로 설정한다.  
분류 태스크의 특성상 JSON이나 Markdown이 아닌 단일 카테고리명을 출력하도록 프롬프트를 설계하여  
후처리 파싱 없이 즉시 활용할 수 있도록 한다.

---

## 4. 실행 환경별 구동 가능 모델

| 환경 | VRAM | 정밀도 | 실행 가능 모델 |
|---|---|---|---|
| RTX 3080 (로컬/Ollama) | 12GB | INT4 (기본) | 3종 모두 구동 가능 |
| Colab 무료 (T4) | 16GB | INT4/INT8 | 3종 모두 구동 가능 |
| Colab 무료 (T4) | 16GB | FP16 | Qwen3-8B, EXAONE-3.5-7.8B, Ministral-8B 모두 OOM 위험 |

> Ollama 기본 양자화(Q4_K_M 등)로 3종 모두 RTX 3080에서 구동 가능  
> 속도 비교는 동일 양자화 조건(INT4)에서 수행하여 공정성 확보

---

## 5. 평가 지표

| 지표 | 설명 |
|---|---|
| 카테고리 분류 정확도 | 정답 카테고리 대비 모델 출력 일치율 (Exact Match) |
| 응답 속도 | 입력→출력 완료까지 소요 시간 (ms), **5초 이내 여부** |
| 출력 형식 준수율 | 카테고리명만 출력하는지 vs 불필요한 설명이 포함되는 비율 |
| 한국어 문서 분류 정확도 | 물류 도메인 한국어 문서에 대한 카테고리 분류 정확도 |
| 한영 혼용 문서 처리 | 한국어 본문 + 영문 해운 용어 혼용 문서의 분류 정확도 |
| 한글/영문 프롬프트 성능 차이 | 동일 문서에 대해 한글 프롬프트 vs 영문 프롬프트의 정확도·속도 차이 |

---

## 6. 탈락 모델 및 사유

| 모델 | 탈락 사유 |
|---|---|
| Qwen2.5-7B-Instruct | Qwen3-8B의 같은 계열 구세대 (학습 데이터 18T vs 36T, 29개 vs 119개 언어). 상위호환이 존재하므로 슬롯 낭비 |
| Gemma 3 12B IT (QAT) | Q4 기준 ~8GB로 구동 가능하나, 카테고리 단답 출력에 12B 품질이 불필요하고 8B 대비 속도 열세 |
| Ministral 3 8B (2512) | 비전 인코더 0.4B 포함 멀티모달 모델. OCR 텍스트만 입력하는 분류에 비전은 불필요한 오버헤드 |
| Qwen3-14B / 32B | RTX 3080 VRAM(12GB) 초과, FP16 기준 28GB+ 필요 |
| Qwen3-4B | 1주차에서 Qwen3.5-4B로 이미 실험 예정, 중복 회피 |
| Qwen3-1.7B / 0.6B | 파라미터 부족으로 카테고리 분류 정확도 저하 우려 |
| Gemma-2-9B-it | FP16 ~18GB로 RTX 3080 OOM, Colab T4에서도 빡빡 |
| Phi-4-mini-instruct (3.8B) | 한국어 성능 미검증, 사실 지식 부족으로 문서 유형 판별에 불리 |
| SmolLM3-3B | 유럽어 중심 학습, 한국어 지원 약함 — 한국어 문서 분류 부적합 |
| Llama-3.1-8B-Instruct | 한국어 공식 미지원 (8개 언어만 지원), 한국어 문서 분류 정확도 저하 우려 |
| Mistral-7B-Instruct-v0.3 | Ministral-8B의 이전 세대, 구세대 중복 |
| Mistral-Small-24B-Instruct | 24B급으로 RTX 3080 구동 불가 |
| DeepSeek-R1-Distill-Qwen-7B | Reasoning 특화 모델, Instruct(Non-thinking) 요구사항에 부적합 |
| EXAONE 4.0-1.2B | 1주차에서 한국어 기준점으로 이미 선정, 카테고리 분류 전용 비교군으로는 파라미터 부족 |
| HyperCLOVA X SEED 8B | 텍스트 전용 Instruct 8B 모델 없음 (Omni-8B은 멀티모달, Text-Instruct는 0.5B/1.5B만 존재) |
| Mistral NeMo 12B | 12B급으로 RTX 3080 FP16 OOM, INT4에서도 8B 대비 속도 열세 |

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
| KoBALT 한국어 벤치마크 논문 | https://arxiv.org/html/2505.16125 |
| EXAONE-3.5-7.8B-Instruct 모델 카드 | https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct |
| EXAONE 3.5 Ollama | https://ollama.com/library/exaone3.5 |
| EXAONE 3.5 기술 보고서 | https://arxiv.org/abs/2412.04862 |
| Ministral-8B-Instruct 모델 카드 | https://huggingface.co/mistralai/Ministral-8B-Instruct-2410 |
| Ministral-8B vs Qwen2.5 비교 토론 | https://huggingface.co/mistralai/Ministral-8B-Instruct-2410/discussions/5 |
| Self-Hosted LLM Leaderboard 2026 | https://onyx.app/self-hosted-llm-leaderboard |
| Best Open-Source SLMs 2026 | https://www.bentoml.com/blog/the-best-open-source-small-language-models |
| Best Open-Source LLM for Korean | https://www.siliconflow.com/articles/en/best-open-source-llm-for-korean |
| LLM Speed Benchmarks | https://www.inferless.com/learn/exploring-llms-speed-benchmarks-independent-analysis---part-3 |
| RTX 3080 Ti LLM 벤치마크 | https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-3080-ti/ |
| LocalScore.ai 모델별 속도 | https://www.localscore.ai/model/1 |
