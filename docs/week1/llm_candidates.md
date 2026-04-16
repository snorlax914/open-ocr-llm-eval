# 감자빵 1주차 보고서 - LLM

본 프로젝트의 파이프라인(OCR → sLLM 분류/요약/필드 추출/검증)에 적합한  
오픈소스 경량 LLM 후보를 조사하여 정리한다.

조사 기준일: 2026년 4월 13일

---

## 1. LLM 후보 모델 목록

### 1.1. LLM 후보 (4개)

OCR을 통해 추출된 텍스트를 입력으로 받아 분류, 요약, 필드 추출, 검증을 수행하는 모델이다.
후보 4개는 역할이 겹치지 않도록 `범용 주력`, `한국어 특화`, `오픈소스 비교군`, `최신 경량 다국어 비교군`으로 나누어 선정했다.

#### 1) Qwen3.5-4B (Alibaba) — 범용 주력 후보

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Qwen3.5-4B | 4B | 2026년 3월 | 262K (1M 확장 가능) | Apache 2.0 |

- 다국어 지원 폭이 넓고(201개 언어), OCR 결과를 요약·분류·필드 추출하는 용도에 잘 맞음
- 공식 벤치마크에서 동급 대비 강한 성능으로 보고됨 (MMLU-Pro 79.1%, GPQA Diamond 76.2%)
- Markdown 형식 출력 안정적, 장문 컨텍스트 처리 가능
- 4B급 대비 262K 컨텍스트가 커서 문단 수가 많은 OCR 결과를 한 번에 넣고 후처리하기 좋음
- 라이선스가 Apache 2.0이라 성능이 충분할 경우 후속 MVP 검증으로 이어가기 쉬움

> **버전 선택 근거**: Qwen3.5는 Dense 모델 0.8B, 2B, 4B, 9B, 27B와 MoE 모델 35B-A3B, 397B-A17B의 총 7종으로 제공된다.
> 9B는 MMLU-Pro 82.5, GPQA Diamond 81.7로 4B(79.1, 76.2)보다 우수하나 bf16 ~18GB로 T4 16GB를 초과하여 양자화가 필수다.
> 27B 이상은 T4 VRAM을 크게 초과하고, MoE 모델(35B-A3B, 397B-A17B)은 총 파라미터 대비 메모리 요구가 높아 Colab 무료 티어에 맞지 않는다.
> 4B는 MMLU-Pro 79.1, GPQA Diamond 76.2, IFEval 89.8, OCRBench 85.0으로 문서 이해·구조화 출력에 충분한 성능을 보이며,
> bf16 기준 ~8GB로 T4에 여유 있게 적재되는 최적 지점이다.

**Colab 실행**: 무료 티어에서 T4 환경 기준 bf16 실험 가능 (실제 GPU 할당은 시점·계정 상태에 따라 변동)

---

#### 2) EXAONE 4.0-1.2B (LG AI Research) — 한국어 특화

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| EXAONE 4.0-1.2B | 1.2B | 2025년 7월 | 65K | 비상업(NC) — 상용 불가 |

- EXAONE 최신 세대(4.0)의 경량 모델로, reasoning/non-reasoning 모드 전환을 지원
- 한국어 벤치마크: KMMLU-Pro 42.7(reasoning), KMMLU-Redux 46.9(reasoning), KSM 60.6(reasoning), Ko-LongBench 69.8(non-reasoning)
- IFEval 74.7(non-reasoning)로 구세대 3.5-2.4B(73.6)를 1.2B로 상회
- 65K 컨텍스트로 긴 OCR 결과 처리에 유리 (3.5-2.4B는 32K)
- Qwen3.5-4B와 한국어 성능 정면 비교용 핵심 후보
- **비상업(NC) 라이선스로 상용 서비스 적용 불가** — 실험 단계에서 한국어 품질 기준점 역할로만 활용
- 범용 모델이 한국어 행정·업무 문서를 충분히 따라오는지 확인하기 위한 `한국어 기준점` 역할을 수행함

> **버전 선택 근거**: EXAONE 시리즈는 3.5(2.4B/7.8B/32B), Deep(2.4B/7.8B/32B), 4.0(1.2B/32B), 4.5(33B VLM)의 4세대로 제공된다.
> EXAONE 3.5-2.4B는 파라미터가 2배이나 구세대(2024.12)이고, IFEval 73.6으로 4.0-1.2B(74.7)보다 낮으며 KMMLU 계열 벤치마크가 미공개라 정량 비교가 어렵다.
> EXAONE Deep 2.4B는 MATH-500 92.3, AIME 2024 52.5로 수학·코딩 추론에 특화된 모델이며, 문서 분류·요약용 벤치마크(IFEval, MT-Bench 등)가 공개되지 않아 본 태스크 적합성을 판단하기 어렵다.
> EXAONE 4.0-32B, 4.5-33B는 T4에서 구동 불가하다.
> 4.0-1.2B는 IFEval 74.7, KMMLU-Pro 42.7, KMMLU-Redux 46.9, KSM 60.6, Ko-LongBench 69.8로 한국어 벤치마크가 가장 폭넓게 공개되어 있고, bf16 ~2.5GB로 T4에 가장 여유 있게 적재된다.

**Colab 실행**: 무료 티어에서 T4 환경 기준 실험 가능 (실제 GPU 할당은 시점·계정 상태에 따라 변동)

---

#### 3) Gemma 4 E4B (Google) — 오픈소스 비교군

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Gemma 4 E4B | 4.5B effective / 8B with embeddings | 2026년 4월 초 | 128K | Apache 2.0 |

- 과제 예시에 명시된 Gemma 계열의 최신 모델
- Per-Layer Embeddings(PLE) 구조로, 연산에 사용되는 유효 파라미터는 4.5B이고 임베딩 포함 전체는 8B
- Apache 2.0 라이선스로 상용 MVP까지 활용 가능 → EXAONE NC 라이선스 제약의 대안
- Google 계열 최신 오픈 모델을 포함해 특정 벤더 편향 없이 후보군을 구성하는 의미가 있음

> **버전 선택 근거**: Gemma 4는 Dense 모델 E2B, E4B, 31B와 MoE 모델 26B-A4B의 4종으로 제공된다.
> E2B는 MMLU-Pro 60.0, MMMU-Pro 44.2로 E4B(69.4, 52.6) 대비 문서 이해 품질이 크게 떨어진다.
> 26B-A4B는 MMLU-Pro 82.6으로 성능은 우수하나 총 파라미터 25.2B로 T4 VRAM을 초과한다.
> 31B는 MMLU-Pro 85.2로 최고 성능이지만 역시 T4 구동 불가다.
> E4B는 MMLU-Pro 69.4, GPQA Diamond 58.6, MMMLU 76.6, LiveCodeBench v6 52.0으로 소형 모델 중 충분한 성능을 보이며,
> 임베딩 포함 8B이지만 유효 연산은 4.5B 수준이라 T4에서 구동 가능한 최적 지점이다.

**Colab 실행**: 무료 티어에서 T4 환경 기준 실험 가능 (실제 GPU 할당은 시점·계정 상태에 따라 변동)

---

#### 4) Ministral 3 3B (Mistral AI) — 최신 경량 다국어 비교군

| 모델 | 파라미터 | 출시 | 컨텍스트 | 라이선스 |
|---|---|---|---|---|
| Ministral 3 3B | 3.4B (+ 410M ViT) | 2025년 12월 | 256K | Apache 2.0 |

- Mistral 3 제품군의 초경량 모델로, 3B급 대비 256K 컨텍스트를 제공함
- 비전(ViT) 인코더가 내장되어 있으나, 이번 프로젝트에서는 `OCR 후 텍스트 입력 전용 LLM`으로 사용하여 Mistral 계열 텍스트 성능을 확인함
- Apache 2.0 라이선스라 상용 적용 가능성이 높고, EXAONE의 NC 제약을 보완하는 추가 대안이 됨
- Qwen과 Gemma 외에 Mistral 계열까지 포함함으로써 후보군의 벤더 다양성과 비교 설득력이 커짐

> **버전 선택 근거**: Ministral 3 제품군은 3B, 8B, 14B의 3종으로 제공되며, 각각 Base/Instruct/Reasoning 변형이 있다.
> 8B는 MMLU 5-shot 76.1, GPQA Diamond 66.8, AIME25 78.7로 3B(70.7, 53.4, 72.1)보다 우수하나 bf16 기준 ~24GB로 T4 VRAM을 초과한다.
> 14B는 MMLU 5-shot 79.4, GPQA Diamond 71.2, AIME25 85.0으로 최고 성능이지만 T4 VRAM을 크게 초과한다.
> 3B는 MMLU 5-shot 70.7, MMLU-Redux 73.5, MATH Maj@1 83.0, Multilingual MMLU 65.2로 3B급 대비 강한 성능을 보이며,
> bf16 기준 ~7.6GB로 T4에 여유 있게 적재되는 가장 경량의 선택지다.

**Colab 실행**: 무료 티어에서 T4 환경 기준 bf16 실험 가능 (실제 GPU 할당은 시점·계정 상태에 따라 변동)

---

### 1.2. 최종 후보 비교 요약

| 기준 | Qwen3.5-4B | EXAONE 4.0-1.2B | Gemma 4 E4B | Ministral 3 3B |
|---|---|---|---|---|
| 한국어 성능 | ★★★★ | ★★★★★ | ★★★ | ★★★ |
| Markdown 출력 품질 | ★★★★★ | ★★★★ | ★★★★ | ★★★★ |
| 문서 이해력 | ★★★★★ | ★★★★ | ★★★★ | ★★★★ |
| Colab 실행 용이성 | ★★★★ | ★★★★ | ★★★★★ | ★★★★★ |
| 상용 라이선스 | ✅ Apache 2.0 | ❌ NC (상용 불가) | ✅ Apache 2.0 | ✅ Apache 2.0 |

---

## 2. 실험 구조

### OCR + 텍스트 LLM (4개)

| 순위 | 모델 | 역할 |
|---|---|---|
| 1 | **Qwen3.5-4B** | 범용 주력 후보 — 다국어 + 구조화 출력 + 컨텍스트 균형 최우수 |
| 2 | **EXAONE 4.0-1.2B** | 한국어 특화 검증 — Qwen과 한국어 성능 정면 비교 (상용 불가, 실험 기준점) |
| 3 | **Gemma 4 E4B** | 오픈소스 비교군 — 과제 예시 모델 계열, Apache 2.0 상용 대안 |
| 4 | **Ministral 3 3B** | 경량 다국어 비교군 — Mistral 계열 포함, 긴 컨텍스트와 상용 라이선스 확보 |

```
문서 이미지 → OCR 모델 → 추출 텍스트 → 텍스트 LLM → Markdown 결과
대상: Qwen3.5-4B, EXAONE 4.0-1.2B, Gemma 4 E4B, Ministral 3 3B
```

본 프로젝트의 최종 출력 형식은 **Markdown**으로 설정한다.  
Markdown은 JSON 대비 파싱 실패 리스크가 낮고, 사람이 직접 검수(human-in-the-loop)하기에 적합하다.

비교 시 동일 문서·동일 프롬프트·동일 평가 지표를 적용하여 모델 간 성능 차이를 분석할 수 있다.

---

## 3. Colab 환경별 실행 가능 모델

| 환경 | VRAM | 실행 가능 모델 |
|---|---|---|
| Colab 무료 (T4) | 16GB | Qwen3.5-4B, EXAONE 4.0-1.2B, Gemma 4 E4B, Ministral 3 3B |

> 선정된 후보 4종 모두 무료 티어 T4 환경 기준 양자화 없이 구동 가능  
> 단, 실제 GPU 할당은 시점과 계정 상태에 따라 변동할 수 있음

---

## 4. 평가 지표

| 지표 | 설명 |
|---|---|
| Markdown 서식 정확도 | 제목/표/리스트 등 요구한 Markdown 구조가 올바르게 생성되는 비율 |
| 정보 추출 정확도 (Field Accuracy) | 추출 대상 필드가 Markdown 내에 정확히 포함된 비율 |
| 서식 일관성 | 동일 프롬프트 반복 시 출력 서식이 일관되게 유지되는 비율 |
| 한국어 작문 품질 | 사람 평가 1~5점 (자연스러운 문장, 정보 보존도, 간결성) |
| 처리 속도 | tokens/sec, 문서 1건당 평균 처리 시간 |
| VRAM 사용량 | Peak GPU 메모리 (nvidia-smi 측정) |

---

## 5. 탈락 모델 및 사유

| 모델 | 탈락 사유 |
|---|---|
| Mistral Small 4 | 최신 모델이지만 119B total / 6.5B active 규모라 `경량 Colab 실험` 취지와 맞지 않음 |
| Mistral NeMo 12B | 다국어 장점은 있으나 2024 세대 12B 모델이라 최신성·실험 경량성 모두 Ministral 3 3B보다 불리 |
| Qwen3.5-9B | bf16 ~18GB로 T4 초과 → 4B로 먼저 검증 후 필요시 스케일업 |
| Qwen3.5-27B / 35B-A3B / 397B-A17B | T4 VRAM을 크게 초과, Colab 무료 티어 구동 불가 |
| EXAONE 3.5-2.4B | 구세대(2024.12), IFEval 73.6으로 4.0-1.2B(74.7)보다 낮고 KMMLU 계열 벤치마크 미공개, 32K 컨텍스트 |
| EXAONE 3.5-7.8B/32B | 7.8B는 bf16 ~16GB로 T4 OOM 위험, 32B는 T4 구동 불가 |
| EXAONE Deep 2.4B/7.8B/32B | MATH-500 92.3, AIME 52.5 등 수학·코딩 추론 특화, 문서 분류·요약용 벤치마크(IFEval, MT-Bench) 미공개 |
| EXAONE 4.0-32B | T4 VRAM 초과, Colab 구동 불가 |
| EXAONE 4.5-33B | 33B 단일 사이즈(VLM)로만 공개, Colab 구동 불가 |
| Ministral 3 8B | MMLU 76.1, GPQA Diamond 66.8로 3B(70.7, 53.4)보다 우수하나 bf16 ~24GB로 T4 초과 |
| Ministral 3 14B | MMLU 79.4, GPQA Diamond 71.2로 최고 성능이나 T4 VRAM을 크게 초과 |
| Gemma 4 E2B | MMLU-Pro 60.0, MMMU-Pro 44.2로 E4B(69.4, 52.6) 대비 성능 부족 |
| Llama 3.2-3B | 한국어 공식 미지원, 이 프로젝트에서 의미 없음 |
| Qwen2.5-VL-3B / 7B | Qwen3.5가 후속 세대, 중복 |
| Phi-4-multimodal | 한국어 성능 부족 |

---

## 6. 리서치 참고 모델 (실험 대상 외)

아래 모델들은 성능은 우수하나 Colab 환경 구동이 어려워 리서치 참고용으로만 기록한다.

| 모델 | 파라미터 | 비고 |
|---|---|---|
| Mistral Small 4 | 119B total (6.5B active) | 2026년 3월 공개, 성능·기능은 강하지만 본 과제의 Colab 경량 실험 범위를 넘어감 |
| EXAONE 4.0-32B | 32B | 2025년 7월 공개, 추론 모드 통합, T4 구동 불가 |
| EXAONE 4.5 | 33B (VLM) | 2026년 공개, LG AI Research 최초 오픈웨이트 VLM, Colab 구동 어려움 |
| K-EXAONE | 236B total (23B active) | MoE 구조, LG AI Research 대규모 다국어 모델, Colab 구동 불가 |
| Llama 4 Scout | 17B active (MoE) | 10M 컨텍스트, H100 1장 필요 |
| Qwen3-VL-32B | 32B | VLM 최상위 성능, Colab Pro에서도 양자화 필요 |
| Qwen3.5-27B | 28B | Dense 모델, T4 VRAM 크게 초과 |
| Qwen3.5-35B-A3B (MoE) | 35B (3B active) | MoE 구조, 총 파라미터 대비 메모리 요구 높음 |
| Qwen3.5-397B-A17B (MoE) | 397B (17B active) | 최상위 MoE, 로컬 실행 비현실적 |
| DeepSeek-V3.2 | 671B (37B active) | MMLU 94.2%, MIT 라이선스, 로컬 실행 비현실적 |
