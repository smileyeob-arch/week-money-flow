# 키움 데이터 수집기 연결 단계

이 폴더는 API 연동 전 준비 단계입니다.

- 키움 REST API 사용 신청 및 App Key / Secret 발급
- GitHub Actions Secrets에 `KIWOOM_APP_KEY`, `KIWOOM_SECRET_KEY` 등록
- 공식 API 가이드에서 일별 종목별 거래대금/주가 이력 조회 TR의 요청 필드, 응답 필드, 연속조회 규칙 확인
- 일별 종목 거래대금 데이터를 거래일마다 누적한 뒤 금요일 주간 합산
- 종목코드-섹터 매핑(`sectors.csv`)을 적용해 테마별 합계 계산

중요: `ka10031`은 당일 거래대금 상위 조회로 안내되어 있으므로, 과거 5거래일을 주간 합산하려면 일별 이력 조회 API 또는 매일 저장한 스냅샷이 필요합니다. TR의 정확한 필드와 호출 제한을 검증하기 전에는 임의 endpoint를 넣지 않습니다.

키움 공식 가이드: https://openapi.kiwoom.com/m/guide/apiguide
공식 예제 저장소: https://github.com/Kiwoom-Securities/Kiwoom-REST-API
