# 의약품 심의자료 진위·오탈자 검증기 v4.0

## 배포
GitHub에 push 후 Streamlit Community Cloud에서 이 저장소를 연결하면 됩니다.
로컬 Python 실행을 전제로 하지 않습니다.

## API 키
코드에 하드코딩하지 않습니다. 앱 사이드바에서 직접 입력합니다(비밀번호 입력창, 세션 동안만 유지).
- 식약처(MFDS) 인증키: 디코딩된 키
- 심평원(HIRA) 인증키: 디코딩된 키

## 확인된 API 엔드포인트
- MFDS 목록조회: `DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07`
- MFDS 상세조회: `DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06`
- HIRA 약가조회: `dgamtCrtrInfoService1.2/getDgamtList`

## 로컬 테스트
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 구조
- `app.py`: Streamlit 진입점 (3개 탭)
  - 🔍 의약품 조회: 검색 → 선택표 → 추가 항목 체크 → 조회 → 상세/비교표/DUR 확인
  - 📋 비교표 입력: PPTX/XLSX/붙여넣기 3종, 구조 확인 화면
  - 🧾 검증 · Claude 자료: 규칙기반 1차 검증 + Claude 웹용 프롬프트 생성 + 결과 재파싱
- `modules/mfds_hira_core.py`: 검증된 MFDS/HIRA 조회, NB_DOC_DATA 파싱, DUR 확인 핵심 로직
  (사용자가 이미 별도로 검증한 코드를 그대로 재사용)
- `modules/ui_table.py`: 컬럼 리사이즈 가능한 결과 표 렌더링
- `modules/table_parsers/`: PPTX/XLSX/붙여넣기 파서 + 공통 스키마 정규화
- `modules/rule_check.py`: 5장 규칙기반 1차 검증 (기본정보/숫자단위/약가만 자동 확정, 서술형은 Claude로 위임)
- `modules/prompt_builder.py`: Claude 웹용 프롬프트 생성 (검증 원칙 원문 요약 없이 포함)
- `modules/result_parser.py`: Claude 웹 응답(마크다운표/JSON) 재파싱
- `modules/utils.py`: 공통 정규화 유틸

## 캐시 파일
`load_permitted_drugs`가 하루 1회 식약처 전체 허가목록을 받아 다음 파일들로 캐시합니다
(Streamlit Cloud 재시작 시 초기화됨 — 정상적인 동작입니다):
- `허가목록_원본.csv`, `허가목록_메타.json`
- `cache_약가_코드별.json`, `cache_약가_이름별.json`, `cache_상세정보.json`, `cache_약효분류.json`
