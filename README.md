# tax-rag

취득세·재산세 업무를 위한 전문 RAG 시스템 스캐폴드입니다. 공개 법률 데이터는 `korean-law-mcp`로 실시간 조회하고, 비공개 업무 지식은 SQLite와 ChromaDB에 저장한 뒤, 두 결과를 결합하여 Anthropic Claude API로 최종 답변을 생성합니다.

## 주요 구성
- 공개 데이터: 판례, 법령, 심판례
- 비공개 데이터: 민원처리, 전산적용, 내부 이론
- 백엔드: FastAPI
- 저장소: SQLite + ChromaDB
- 답변 생성: Anthropic Claude API

## 아키텍처 개요
1. 사용자가 질의합니다.
2. `korean-law-mcp`가 공개 법률 데이터를 실시간 조회합니다.
3. SQLite + ChromaDB가 비공개 문서와 실무 지식을 검색합니다.
4. RAG 파이프라인이 두 검색 결과를 결합해 Claude로 답변을 생성합니다.

## 빠른 시작
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

## 환경 변수
`.env.example` 기준:

- `ANTHROPIC_API_KEY`: Anthropic API 키
- `LAW_OC`: `korean-law-mcp` 연동용 인증값
- `SQLITE_PATH`: 비공개 문서 SQLite 파일 경로
- `CHROMA_PATH`: ChromaDB 저장 경로

## korean-law-mcp 준비
`korean-law-mcp`는 npm 패키지이므로 Node.js 환경이 필요합니다. 프로젝트 정책에 맞게 `npx korean-law-mcp` 형태로 실행하거나 전역 설치 후 연동하면 됩니다.

## 프로젝트 구조
```text
tax-rag/
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── database.py
│   ├── private_store.py
│   ├── law_search.py
│   ├── rag.py
│   └── routers/
│       ├── __init__.py
│       ├── documents.py
│       ├── search.py
│       └── chat.py
├── data/
│   └── private/
│       └── .gitkeep
├── frontend/
│   └── .gitkeep
├── scripts/
│   └── seed_sample.py
└── tests/
    └── test_rag.py
```

## 문서 스키마
| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | `str` | UUID |
| `category` | `str` | `precedent`, `tribunal`, `case`, `civil`, `theory`, `statute` |
| `is_private` | `bool` | 기본값 `true` |
| `title` | `str` | 문서 제목 |
| `source` | `str` | 출처 |
| `content` | `str` | 법률 내용 본문 |
| `practical` | `str` | 전산 적용 방법 등 실무 메모, 선택 |
| `date` | `str` | `YYYY-MM-DD` |
| `tags` | `list[str]` | 태그 목록 |
| `created_at` | `datetime` | 생성 시각 |
| `updated_at` | `datetime` | 수정 시각 |

## 카테고리
- `precedent`: 법원 판결
- `tribunal`: 조세심판원 결정
- `case`: 질의회신, 유권해석, 참고 사례
- `civil`: 직접 처리한 민원, 해결 기록
- `theory`: 학설, 해석론, 내 이론
- `statute`: 법률, 시행령 조문

## 다음 단계 제안
- FastAPI 앱 엔트리포인트와 설정 로더 구현
- SQLite 스키마와 ChromaDB 컬렉션 초기화
- `korean-law-mcp` 연동 모듈 작성
- 통합 검색 및 질의응답 API 작성
