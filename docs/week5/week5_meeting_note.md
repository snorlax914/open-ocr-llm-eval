## **1. 회의 정보**

---

- **회의 목적: 4주차 피드백 반영 및 통합 MVP 서비스 구현 방향 설정**
- **회의 시간: 2026. 05. 08**

## **2. 회의 내용**

---

### **1. MVP 핵심 기능 및 범위**

- 핵심 파이프라인: 문서 업로드 → OCR 실행 → 카테고리 분류 → 마크다운 Chunking → 화면 출력
- 구현 범위: 디자인은 신경 쓰지 않고 파이프라인 단위 동작 위주
- 후속 과제: MVP 완성 후 기능 보완 (예: HTML → Markdown 변환 등)

### **2. 기술 스택 및 아키텍처**

- Frontend: Next.js
- Backend: FastAPI (프론트/백엔드 분리 구성)
- OCR: PaddleOCR
- LLM: Qwen3:8B 
- 구조: Frontend ↔ Backend API 통신, Backend에서 OCR·LLM·Chunking 로직 서빙
- 참고 사항: 분류 LLM과 답변 LLM 분리하지 않고 진행

### **3. 일정 및 진행 방식**

- 5~7주차: MVP 서비스 구현 (총 3회 과제로 분할 진행)
- 6~8주차: 매주 피드백 + 수정 반복
- 진행 방식: MVP 구현 → 피드백 → 보완 사이클 반복

### **4. 제약 사항 및 환경**

- 하드웨어: 회사 측 추가 지원 없음, 기존 환경 내에서 구현
- 데이터: 회사 보유 문서 데이터 제공 불가, AI Hub 공개 데이터셋 지속 활용

## **3. 결정사항**

---

- MVP 핵심 파이프라인 구현 우선 (디자인·실무형 완성도보다 동작 가능한 파이프라인 중심)
- Frontend: Next.js / Backend: FastAPI 구조로 분리 구성
- OCR: PaddleOCR, LLM: Qwen3:8B 유지
- 5~7주차 MVP 구현 + 6~8주차 피드백 반영 사이클 진행
- 마크다운 Chunking은 이번 주 리포트 기반 실험 병행

## **4. 해야 할 일**

---

[] 통합 MVP 서비스 구현

    - Frontend (Next.js): 파일 업로드 영역 + 처리 상태 인디케이터 + 결과 대시보드 구현  
    - 결과 대시보드에서 OCR 추출 전체 마크다운 + 분할된 Chunk 확인 가능하도록 구성  
    - Backend (FastAPI): OCR·LLM·Chunking 로직 API 서빙 + Frontend 통신용 엔드포인트 설계  
 

[] 핵심 기술 고도화 

    - 마크다운 Chunking 전략 비교 실험 (Recursive / Markdown Header / Token / Semantic)
    - Overlap 비율별 성능 비교 + 표 구조 보존 실험
