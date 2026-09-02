# 의약품 심의자료 진위·오탈자 검증기 v4.0

## 배포
GitHub에 push 후 Streamlit Community Cloud에서 이 저장소를 연결하면 됩니다.
로컬 Python 실행을 전제로 하지 않습니다.

## API 키 설정
코드에 하드코딩하지 않습니다. Streamlit Cloud의 "Secrets" 설정에 아래를 추가하세요.

```
MFDS_SERVICE_KEY = "..."
HIRA_SERVICE_KEY = "..."
```

secrets가 없으면 앱 사이드바에서 직접 입력(비밀번호 입력창)할 수 있습니다.

## 아직 확인이 필요한 부분 (실제 서비스키로 검증 필요)
- `modules/api_client.py`의 MFDS/HIRA 엔드포인트·파라미터명은 공개 스펙 기준으로 작성했습니다.
  이 개발 환경은 data.go.kr 계열 도메인에 대한 네트워크 호출이 막혀 있어 실제 응답으로
  테스트하지 못했습니다. 실제 키로 1회 스모크 테스트 후 필드명(`ITEM_NAME`/`itemName` 등
  대소문자/표기 차이)을 응답에 맞게 보정해야 할 수 있습니다.
- `modules/field_specs.py`의 `EXTRA_FIELD_SPECS` keywords는 NB_DOC_DATA 실제 title 표기에
  맞춰 보정이 필요할 수 있습니다.
- 이전 세션에서 이미 검증된 MFDS/HIRA 호출 코드가 있다면, 그 파일을 업로드해주시면
  `api_client.py`/`field_specs.py`를 그 코드로 교체(재사용)하겠습니다 — 명세서 3장 원칙.

## 로컬 테스트
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 구조
- `app.py`: Streamlit 진입점 (3개 탭). 원래 `app_통합.py`였으나, zip 압축 해제 시
  한글 파일명이 깨지는 문제를 피하기 위해 영문 파일명으로 변경함.
- `modules/api_client.py`: MFDS 목록/상세, HIRA 약가 조회
- `modules/field_specs.py`: EXTRA_FIELD_SPECS, NB_DOC_DATA 섹션 파싱
- `modules/matching.py`: 바코드-mdsCd 8자리 매칭 (제품명만으로 동일 제품 확정 금지)
- `modules/utils.py`: 정규화 유틸
- `modules/table_parsers/`: PPTX/XLSX/붙여넣기 파서 + 공통 스키마 정규화
- `modules/rule_check.py`: 5장 규칙기반 1차 검증 (기본정보/숫자단위/약가만 자동 확정)
- `modules/prompt_builder.py`: Claude 웹용 프롬프트 생성 (원문 요약 없이 그대로 포함)
- `modules/result_parser.py`: Claude 웹 응답(마크다운표/JSON) 재파싱
