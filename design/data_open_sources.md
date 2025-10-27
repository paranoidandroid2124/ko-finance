# 오픈 데이터/API 후보 정리 (업데이트: 2025-11-27)

## 1. 국내 공공 데이터

### 1.1 한국은행 ECOS (Economic Statistics System)
- **제공 데이터**: 금리, 환율, 통화·신용, 물가, 산업·국제수지 등 거시 지표 전반.
- **형식·인증**: JSON/XML, API Key 필요 → `.env` `ECOS_API_KEY`.
- **엔드포인트 예시**
  ```
  GET https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/json/kr/1/100/{STAT_CODE}/{FREQ}/{START_DATE}/{END_DATE}
  ```
- **주의사항**
  - `list_total_count` 기반으로 100행 단위 페이지 루프 필요.
  - 통계표 코드·항목을 먼저 조회(`StatisticTableList`, `StatisticItemList`) 후 호출.
  - 결과 사용 시 “출처: 한국은행 ECOS” 표기.

### 1.2 통계청 KOSIS OpenAPI
- **제공 데이터**: 인구·고용·물가·지역 등 국가 통계.
- **형식·인증**: JSON 권장, API Key 필요 → `.env` `KOSIS_API_KEY`.
- **엔드포인트 예시**
  ```
  GET https://kosis.kr/openapi/Param/statisticsParameterData.do
      ?method=getList&apiKey=...&orgId=101&tblId=DT_1B41
      &prdSe=Y&startPrdDe=2000&endPrdDe=2024
      &objL1=ALL&format=json&jsonVD=Y
  ```
- **주의사항**
  - 대용량은 연도별로 나눠 호출.
  - 표마다 차원(`objL1~L8`)이 다르므로 ALL/필터 조합으로 오류 처리.

### 1.3 한국수출입은행 환율(OpenAPI)
- **제공 데이터**: 고시환율(AP01), 국제금리(AP02/03) 등.
- **형식·인증**: JSON/XML, `authkey` 필요 → `.env` `KOREAEXIM_AUTH_KEY`.
- **엔드포인트 예시**
  ```
  GET https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON
      ?authkey=...&searchdate=20251027&data=AP01
  ```
- **주의사항**
  - 2025-06-25부터 `oapi.koreaexim.go.kr` 사용.
  - 주말/공휴일은 데이터 없음, 영업일 오전 갱신 → 배치 시간 조절.

### 1.4 국세청 사업자등록 진위/상태 조회
- **제공 데이터**: 사업자등록번호 진위 확인, 휴·폐업/과세유형 정보.
- **형식·인증**: JSON/XML, API Key 필요 → `.env` `NTS_BUSINESS_STATUS_API_KEY`.
- **운영 팁**: 기업 식별 정합성 확보용. 1회 100건, 일 100만건(개발계정 기준).

### 1.5 KIPRIS Plus (특허)
- **제공 데이터**: 국내 특허/디자인/상표 메타·전문.
- **형식·인증**: API Key 필요 → `.env` `KIPRIS_API_KEY` (월 1,000회 무료, 초과 시 과금).
- **주의사항**: 상용 배포 전 요금·약관 확인 필수.

## 2. 글로벌/미국 공공 데이터

### 2.1 SEC EDGAR Data APIs
- **제공 데이터**: 상장사 제출 이력, XBRL 팩트(companyfacts/companyconcept/frames 등).
- **형식·인증**: 무료, API Key 없음. User-Agent 필수 → `.env` `SEC_USER_AGENT`.
- **엔드포인트 예시**
  ```
  GET https://data.sec.gov/submissions/CIK0000320193.json
  GET https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json
  ```
- **주의사항**: 최대 10 req/s 권고, 큐/슬라이딩 윈도우로 쓰로틀링.

### 2.2 FRED (St. Louis Fed)
- **제공 데이터**: 미국 경제 시계열(CPI, 금리 등).
- **형식·인증**: JSON, API Key 필요(추후 `.env` 확장).
- **엔드포인트 예시**
  ```
  GET https://api.stlouisfed.org/fred/series/observations
      ?series_id=CPIAUCSL&api_key=...&file_type=json
  ```

### 2.3 World Bank Indicators
- **제공 데이터**: 전 세계 개발지표 ~16,000개.
- **형식·인증**: JSON, 인증 없이 사용 가능.
  ```
  GET https://api.worldbank.org/v2/country/KOR/indicator/NY.GDP.MKTP.CD?format=json
  ```

### 2.4 OECD SDMX-JSON
- **제공 데이터**: OECD 경기·교육 등 카탈로그 지표, SDMX-JSON.
- **형식·인증**: 인증 없음.
  ```
  GET https://stats.oecd.org/sdmx-json/data/{DATASET}/{KEYS}?contentType=json&startTime=2015&endTime=2025
  ```

### 2.5 IMF SDMX APIs
- **제공 데이터**: IFS 등 IMF 통계.
- **형식·인증**: SDMX JSON, 인증 없음.
  ```
  GET https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/IFS/M.KR.PCPI_IX?startPeriod=2010&endPeriod=2025
  ```

### 2.6 GLEIF LEI API
- **제공 데이터**: LEI(법인 식별자) 및 소유 구조.
- **형식·인증**: 인증 없음. 업데이트 하루 3회, 무료.
  ```
  GET https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]=SAMSUNG
  ```

### 2.7 OpenFIGI Mapping API
- **제공 데이터**: FIGI ↔ ISIN/CUSIP/티커 매핑.
- **형식·인증**: 무인증 저레이트 사용 가능, 대량은 API Key 발급 → `.env` `OPENFIGI_API_KEY`.
  ```
  POST https://api.openfigi.com/v3/mapping
  [
    {"idType":"TICKER","idValue":"005930","exchCode":"XKRX"}
  ]
  ```

## 3. ko-finance 적용 메모
- **Phase 3**: GLEIF, OpenFIGI, ECOS, KOSIS, Eximbank, 국세청 API를 우선 도입해 Pro/Enterprise 기능 강화.
- **Phase 4 이후**: FRED, World Bank, OECD, IMF, KIPRIS 등 추가해 글로벌·거시 커버리지 확장.
- **스키마 권장**
  - `entities`(기업 마스터) + `identifiers`(BRN/LEI/CIK/Figure 등)로 식별자 그래프 구성.
  - `facts_macro`(source, series_code, freq, time, value, unit, vintage), `facts_fin_xbrl` 등 도메인별 테이블 설계.
  - `fx_daily`, `economic_calendar` 등 기능별 보조 테이블.
- **운영 팁**
  - API 키는 Secret Manager로 관리하고 Cloud Scheduler + Cloud Run Job으로 배치 실행.
  - 레이트 제한이 있는 API는 작업 큐/슬라이딩 윈도우로 제어.
  - GCS/BigQuery에 원본 JSON 보관, 정규화 데이터는 Cloud SQL/BigQuery에 적재.
