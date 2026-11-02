# 주간 자금 흐름 분석실

코스피·코스닥 주간 거래대금, 섹터별 합산, 섹터별 상위 종목을 보여주는 개인용 정적 웹 대시보드입니다.

## 현재 포함된 기능
- 코스피/코스닥/전체 시장 필터
- 주차 선택
- 섹터별 주간 거래대금 순위
- 섹터별 종목 거래대금 TOP 5 및 전주 대비
- JSON 임시 업로드
- GitHub Pages 자동 배포 워크플로

## 주의
`data/weekly.json`은 화면 확인용 샘플 데이터입니다. 실제 시세가 아닙니다.
키움 API 연동 전에는 투자 판단에 사용하지 마세요.
API Key/Secret은 HTML/JS/JSON 또는 공개 저장소에 절대 입력하지 마세요.

## GitHub Pages 배포
1. GitHub에서 `weekly-money-flow` 저장소 생성
2. 이 폴더의 파일을 저장소 루트에 업로드하고 `main` 브랜치에 커밋
3. 저장소 Settings → Pages → Build and deployment → Source를 `GitHub Actions`로 선택
4. Actions 탭에서 Deploy workflow 성공 확인
5. `https://깃허브아이디.github.io/weekly-money-flow/` 접속

GitHub Pages는 정적 파일 호스팅입니다. 키움 인증정보를 안전하게 보관하고 API를 호출하려면 별도의 비공개 실행 환경(예: GitHub Actions secrets를 사용하는 수집 workflow)이 필요합니다.

## 키움 연동 다음 단계
키움 REST API는 OAuth 2.0 Client Credentials 방식이며 토큰 유효기간은 24시간입니다. 공식 가이드에서 주간 집계에 필요한 일별 거래대금 이력 TR을 확인한 후 collector를 연결합니다. 단순 당일 거래대금 상위 조회만으로 과거 주간 누적치를 재구성할 수는 없습니다.
