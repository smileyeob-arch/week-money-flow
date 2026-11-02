# 주간 자금 흐름 분석실 - 키움 자동 수집기

## 추가된 기능
- 키움 REST API OAuth 토큰 발급
- ka10032 거래대금 상위 API에서 코스피/코스닥 조회
- 장 마감 후 평일 16:30(KST) 자동 수집
- 일별 원본 저장: `data/daily/YYYY-MM-DD.json`
- 일별 거래대금 합산으로 주간 종목/섹터 순위 갱신: `data/weekly.json`
- GitHub Actions가 데이터 변경분을 자동 커밋하면 Pages 화면도 갱신

## 필수 GitHub Secrets
Repository → Settings → Secrets and variables → Actions에 다음 이름으로 등록:
- `KIWOOM_APP_KEY`
- `KIWOOM_SECRET_KEY`

값은 공개 저장소 파일이나 코드에 절대 넣지 마세요.

## 실행
Actions → Collect weekly money flow → Run workflow로 수동 실행할 수 있습니다.
평일 자동 실행은 UTC 07:30 = 한국시간 16:30입니다.

## 섹터 분류
`sectors.csv`에 `code,name,market,sector` 형식으로 종목코드와 섹터를 추가하세요.
매핑되지 않은 종목은 `미분류`로 표시됩니다. 키움 ka10032 응답 자체에는 사용자가 원하는 산업/테마 섹터 분류가 포함되지 않으므로, 이 분류표를 계속 보완해야 합니다.

## 데이터 해석상 주의
`ka10032`는 거래대금 상위 종목 조회 API입니다. 전 종목의 일별 거래대금을 빠짐없이 내려주는 전수 데이터 API가 아닙니다.
따라서 이 수집기는 **매일 거래대금 상위 API 응답에 잡힌 종목의 거래대금을 합산**합니다. 특정 종목이 하루 동안 응답 순위 밖이었다면 그날 거래대금은 주간 합산에서 누락될 수 있습니다.
실제 주간 전 종목 합계를 만들려면 종목별 일별 시세/거래대금 API를 전 종목에 순차 호출하는 별도 수집 설계가 필요하며, 호출 한도·시간·API 이용조건을 확인해야 합니다.

## 현재 버전의 범위
- 실전 API 도메인 사용 (`https://api.kiwoom.com`)
- 주문/매매 기능 없음. 조회 전용입니다.
- `sectors.csv`의 분류 정확도에 따라 섹터 합계의 품질이 달라집니다.
