# tax-rag AGENTS

## 프로젝트 목적
- 취득세·재산세 질의를 위한 전문 RAG 시스템입니다.
- 공개 데이터와 비공개 데이터를 함께 검색한 뒤 Anthropic Claude API로 최종 답변을 생성합니다.

## 데이터 소스 구성
- 공개 데이터: 판례, 법령, 심판례를 `korean-law-mcp`로 실시간 조회합니다.
- 비공개 데이터: 민원처리 기록, 전산 적용 방법, 내부 이론을 SQLite와 ChromaDB에 로컬 저장합니다.
- 응답 생성: 두 소스의 검색 결과를 결합해 Claude가 최종 답변을 작성합니다.

## 기술 스택
- Python 3.12
- FastAPI
- SQLite
- ChromaDB
- Anthropic Claude API
- `korean-law-mcp` (npm 패키지)

## 문서 스키마
- `id`: UUID 문자열
- `category`: `precedent`, `tribunal`, `case`, `civil`, `theory`, `statute`
- `is_private`: 기본값 `true`
- `title`: 문서 제목
- `source`: 출처
- `content`: 법률 내용 본문
- `practical`: 전산 적용 방법 등 실무 메모, 선택값
- `date`: `YYYY-MM-DD`
- `tags`: 문자열 리스트
- `created_at`: 생성 시각
- `updated_at`: 수정 시각

## 카테고리 의미
- `precedent`: 법원 판결
- `tribunal`: 조세심판원 결정
- `case`: 질의회신, 유권해석, 참고 사례
- `civil`: 직접 처리한 민원, 해결 기록
- `theory`: 학설, 해석론, 내부 이론
- `statute`: 법률, 시행령 조문

## 작업 원칙
- `data/private/` 아래 데이터는 비공개 로컬 자산으로 간주합니다.
- 공개 데이터 조회 계층과 비공개 저장 계층을 분리합니다.
- 답변 생성 시 검색 출처를 구분해 추적 가능하게 유지합니다.
