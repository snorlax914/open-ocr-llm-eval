## 2. 모델 선정 기준

본 프로젝트는 문서 OCR 이후 sLLM을 활용하여 분류, 요약, 필드 추출, 검증 등의 작업을 수행하는 구조이므로,  
모델 선정 기준을 **OCR 모델**과 **LLM 모델**로 구분하여 설정한다.

---

### 2.1 OCR 모델 선정 기준

OCR 모델은 이미지 형태의 문서를 텍스트로 변환하는 역할을 수행하며,  
이 단계에서의 품질이 전체 시스템 성능에 직접적인 영향을 미친다.

#### 1) 텍스트 인식 정확도
- 한국어 인식 정확도
- 영어 인식 정확도
- 숫자, 날짜, 코드 및 특수문자 인식 정확도

**평가 방법**
- Character Error Rate (CER): 문자 단위 오류율
- Word Error Rate (WER): 단어 단위 오류율
- 참고 벤치마크: [KORIE](https://www.mdpi.com/2227-7390/14/1/187) — 한국어 영수증 748장 기반 Detection → OCR → IE 3단계 평가

#### 2) 문서 구조 보존 능력
- 문단 구분 유지 여부
- 표, 리스트 등 구조 유지 여부
- 제목/본문/항목 구분 가능성

**평가 방법**
- 구조 보존율: 원본 문서의 표/리스트/문단 수 대비 OCR 결과에서 유지된 비율
- 정성 평가: 샘플 문서 10건 이상에 대해 사람이 구조 유지 수준을 1~5점으로 평가

#### 3) 실행 가능성
- 개인 PC 또는 Google Colab 환경에서 실행 가능 여부
- 요구되는 GPU/CPU 자원이 과도하지 않은지
- 설치 및 실행 난이도

**평가 방법**
- Colab 무료(T4 16GB) / Pro(A100 40GB)에서 정상 구동 여부
- Peak VRAM 사용량 (nvidia-smi 측정)
- 설치 → 첫 추론까지 소요 시간

#### 4) 처리 속도
- 페이지당 처리 시간
- 다수 문서 처리 시 성능 유지 여부

**평가 방법**
- 페이지당 평균 처리 시간 (초)
- 50페이지 연속 처리 시 처리 시간 분산 (성능 저하 여부 확인)

#### 5) 안정성
- 다양한 문서 유형에서 일관된 성능 유지 여부
  - 스캔 문서
  - 저화질 이미지
  - 복잡한 레이아웃 문서

**평가 방법**
- 문서 유형별(스캔/저화질/복잡 레이아웃) CER 편차
- 실패율: 추론 중 에러 또는 빈 결과를 반환하는 비율

#### 6) LLM 후처리 적합성
- 불필요한 노이즈(깨진 문자 등)가 적은지
- 줄바꿈 및 문장 구조가 지나치게 훼손되지 않는지
- LLM 입력으로 바로 활용 가능한 형태인지

**평가 방법**
- 노이즈 문자 비율: OCR 출력 내 깨진 문자·의미 없는 토큰 수 / 전체 토큰 수
- LLM 연계 정확도: 동일 LLM에 각 OCR 결과를 입력했을 때 최종 추출 F1 비교 (OCR 품질 차이가 LLM 성능에 미치는 영향 간접 측정)

---

### 2.2 LLM 모델 선정 기준

LLM 모델은 OCR을 통해 추출된 텍스트를 기반으로  
문서 이해 및 정보 가공(분류, 요약, 필드 추출, 검증 등)을 수행한다.

#### 1) 문서 이해 능력
- OCR 결과와 같이 정제되지 않은 텍스트도 해석 가능한지
- 문맥을 유지하며 문서를 이해할 수 있는지

**평가 방법**
- 참고 벤치마크: [KLUE-MRC](https://github.com/KLUE-benchmark/KLUE) (Machine Reading Comprehension) — 한국어 문서 독해력 측정
- 자체 평가: OCR 노이즈가 포함된 텍스트에 대해 QA 정답률 (Exact Match, F1)

#### 2) 정보 추출 및 구조화 능력
- 필요한 정보를 정확하게 추출하는지
- JSON, key-value 형태 등 구조화된 출력 생성 가능 여부

**평가 방법**
- 참고 벤치마크: [ExtractBench](https://arxiv.org/abs/2602.12247) 방식 적용
  - **Valid JSON Rate**: 출력이 파싱 가능하고 스키마를 준수하는 비율 (`json.loads()` + 스키마 검증)
  - **Pass Rate**: 필드별 정답 대비 정확도 (식별자 → exact match, 금액 → tolerance, 이름 → semantic equivalence)
- 참고 벤치마크: [LLMStructBench](https://arxiv.org/abs/2602.14743) 방식 적용
  - **Field Accuracy**: 개별 필드가 정확히 추출된 비율
  - **Micro-F1**: 모든 key:value 쌍에 대한 precision/recall
  - **DOC (Document Overall Correctness)**: 문서 단위 전체 정답률

#### 3) 요약 / 분류 / 검증 성능
- 문서 요약의 정확성
- 분류 작업 수행 능력
- 잘못된 정보 또는 누락 검출 능력

**평가 방법**
- 요약: ROUGE-L 점수 + 사람 평가 1~5점 (정보 보존도, 간결성)
- 분류: Accuracy, Macro-F1 (참고 벤치마크: [KLUE-TC](https://github.com/KLUE-benchmark/KLUE))
- 검증: 의도적으로 오류를 삽입한 문서에서 오류 검출율 (Precision, Recall)

#### 4) 한국어 처리 성능
- 한국어 문서에 대한 이해도
- OCR 특유의 오류가 포함된 문장에 대한 대응 능력

**평가 방법**
- 참고 벤치마크: [KoBEST](https://huggingface.co/datasets/skt/kobest_v1) — BoolQ, COPA, WiC 등 한국어 추론 5개 태스크
- 참고 벤치마크: [KORIE](https://www.mdpi.com/2227-7390/14/1/187) — 한국어 영수증 필드 추출 F1 (zero-shot 기준 최고 ~25%, 난이도 참고)
- 자체 평가: 한국어 문서 테스트셋에서 필드 추출 F1을 별도 측정하여 영어 결과와 비교

#### 5) 경량성 및 실행 가능성
- 개인 PC 또는 Colab 환경에서 실행 가능한지
- 모델 크기 및 추론 속도가 현실적인 수준인지

**평가 방법**
- Colab 무료(T4 16GB) / Pro(A100 40GB) 구동 가능 여부
- Peak VRAM (GB): nvidia-smi 측정
- 추론 속도: tokens/sec, 문서 1건당 평균 처리 시간
- 양자화(4bit AWQ/GPTQ) 적용 시 성능 저하폭: 원본 대비 F1 차이

#### 6) 출력 형식 안정성
- 동일한 프롬프트에 대해 일관된 출력 제공 여부
- 지정된 출력 형식(JSON 등)을 잘 준수하는지

**평가 방법**
- Valid JSON Rate: 동일 프롬프트 × 동일 문서 10회 반복 시 유효 JSON 비율
- 스키마 준수율: 요구한 키가 모두 포함된 출력 비율
- 출력 일관성: 10회 반복 시 동일 필드 값이 나오는 비율 (재현성)

#### 7) 오픈소스 활용성
- 오픈소스 기반으로 직접 구축 가능한지
- 라이선스 및 사용 편의성

**평가 방법**
- 라이선스 유형: Apache 2.0 / MIT (상용 가능) vs NC (비상업) 구분
- HuggingFace / Ollama 등 주요 플랫폼 지원 여부
- 파인튜닝 가이드 및 커뮤니티 규모 (GitHub Stars, 공식 문서 유무)

---

### 2.3 평가에 활용할 주요 벤치마크 요약

| 벤치마크 | 대상 | 핵심 지표 | 적용 기준 항목 |
|---|---|---|---|
| [ExtractBench](https://arxiv.org/abs/2602.12247) | LLM 구조화 추출 | Valid JSON Rate, Pass Rate | 2.2-2), 2.2-6) |
| [LLMStructBench](https://arxiv.org/abs/2602.14743) | LLM 구조화 추출 | Field Accuracy, Micro-F1, DOC | 2.2-2) |
| [KORIE](https://www.mdpi.com/2227-7390/14/1/187) | 한국어 OCR+IE | 필드별 F1, Accuracy | 2.1-1), 2.2-4) |
| [KLUE](https://github.com/KLUE-benchmark/KLUE) | 한국어 NLU | TC Accuracy, MRC F1, NER F1 | 2.2-1), 2.2-3), 2.2-4) |
| [KoBEST](https://huggingface.co/datasets/skt/kobest_v1) | 한국어 추론 | BoolQ, COPA, WiC Accuracy | 2.2-4) |