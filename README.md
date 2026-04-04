# property-tax-qa

취득세·재산세 질의를 위한 실무형 RAG 프로젝트입니다. 내부 실무자료와 공개 법률자료를 함께 검색해 답변하고, 참조 출처 즐겨찾기, 최근 질의응답 유지, 대량 문서 등록까지 한 화면에서 다룰 수 있습니다.

## 주요 기능
- 공개 검색: 판례, 법령, 심판례를 `law.go.kr` 공개 데이터로 조회
- 내부 검색: 민원처리, 전산 적용 메모, 내부 이론을 SQLite와 ChromaDB에 저장·검색
- 다중 LLM 지원: Anthropic, OpenAI, Gemini, GLM 전환 가능
- 질의응답 UI: 공개 데이터 포함 토글, 참조 출처 더보기, 최근 질의응답 3건 유지
- 참조 출처 즐겨찾기: 검색된 판례·심판례·내부자료를 별표로 저장
- 대량등록: CSV와 Markdown 파일 업로드 지원

## 현재 구조
- 백엔드: FastAPI
- 프론트엔드: React + Vite + Tailwind CSS
- 비공개 저장소: SQLite, ChromaDB
- 공개자료 조회: `law.go.kr` API
- 런타임 연동설정: 화면에서 API 키와 `LAW_OC`를 임시 또는 영구 저장

## 빠른 시작
### 1. 백엔드 실행
```powershell
cd "D:\반종수\AI 관련\05. codex\업무도우미\tax-rag"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

### 2. 프론트 실행
```powershell
cd "D:\반종수\AI 관련\05. codex\업무도우미\tax-rag\frontend"
Copy-Item .env.example .env
npm install
npm run dev
```

브라우저 주소:
- 프론트: [http://localhost:5173](http://localhost:5173)
- 백엔드 상태 확인: [http://localhost:8000/health](http://localhost:8000/health)

## 연동설정
앱의 `연동설정` 화면에서 직접 입력할 수 있습니다.

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `GLM_API_KEY`
- `LAW_OC`
- `LLM_PROVIDER`

지원 방식:
- 이번 실행만 적용
- 로컬에 계속 저장

## `LAW_OC` 안내
공개 법률자료 검색을 쓰려면 `LAW_OC`가 필요합니다.

- 국가법령정보 공동활용 안내: [https://open.law.go.kr/LSO/information/guide.do](https://open.law.go.kr/LSO/information/guide.do)
- OPEN API 활용가이드: [https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsNwJoListGuide](https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsNwJoListGuide)

## 대량등록 형식
### CSV
필수 헤더:
```text
분류,제목,출처,내용,전산적용,날짜,태그
```

### Markdown
여러 문서는 `---` 한 줄로 구분합니다.

```md
# 사실상 취득의 판단 기준 정리
- 분류: 이론
- 출처: 내부 검토 메모
- 날짜: 2026-04-03
- 태그: 취득세;사실상취득
## 내용
사실상 취득은 대금 지급과 사용수익의 이전 등 실질을 기준으로 판단한다.
## 전산적용
잔금일과 점유 이전일을 함께 확인한다.

---
# 증여취득 신고 누락 민원
- 분류: 민원처리
- 출처: 민원처리 내부기록
- 날짜: 2026-04-03
- 태그: 취득세;증여;민원
## 내용
신고 누락 민원 처리 기록
## 전산적용
위택스 보완 입력
```

## 문서 분류
- `precedent`: 판례
- `tribunal`: 심판례
- `case`: 사례
- `civil`: 민원처리
- `theory`: 이론
- `statute`: 법령
- `other`: 기타

## 프로젝트 구조
```text
tax-rag/
├── app/
│   ├── main.py
│   ├── rag.py
│   ├── law_search.py
│   ├── llm_client.py
│   ├── database.py
│   ├── private_store.py
│   └── routers/
├── frontend/
│   ├── src/components/
│   ├── src/pages/
│   └── src/lib/
├── data/private/
├── scripts/
└── tests/
```

## 테스트
백엔드 테스트 예시:
```powershell
pytest tests\test_rag.py tests\test_public_search.py tests\test_favorites.py
```

## 주의 사항
- 실제 비밀키는 `.env` 또는 런타임 설정 파일에만 저장하고 GitHub에는 올리지 않습니다.
- `data/private/` 아래 실제 DB와 로컬 설정 파일은 `.gitignore`로 제외되어 있습니다.
- 프론트 `vite build`는 일부 환경에서 비정상 종료할 수 있어, 개발 서버 기준 검증을 우선 사용하고 있습니다.
