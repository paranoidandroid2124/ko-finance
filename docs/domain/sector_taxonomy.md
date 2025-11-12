# Sector Taxonomy

뉴스/섹터 분석 전반에서 공통으로 사용하는 표준 슬러그와 한글 라벨입니다.  
모든 API·DB·프런트 코드는 이 표를 단일 소스로 참조해야 합니다.

| 슬러그 (slug) | 한글 라벨 |
| --- | --- |
| `semiconductor` | 반도체 |
| `hardware` | 전자장비/디스플레이 |
| `software` | 소프트웨어/SaaS |
| `internet` | 인터넷/플랫폼 |
| `telecom` | 통신 |
| `media` | 미디어/게임/엔터 |
| `mobility` | 모빌리티/완성차 |
| `battery` | 2차전지 |
| `energy` | 에너지/발전/정유 |
| `renewables` | 신재생에너지/수소 |
| `finance` | 금융 |
| `bio` | 바이오/헬스케어 |
| `materials` | 소재/화학/철강 |
| `industrials` | 산업재/기계/조선 |
| `logistics` | 물류/운송 |
| `real_estate` | 부동산/건설/REITs |
| `defense` | 방위산업/항공우주 |
| `consumer` | 소비재 |
| `others` | 기타 (기본값) |

## 기존 슬러그 매핑

| 기존(slug) | 신규(slug) | 비고 |
| --- | --- | --- |
| `misc` | `others` | 기본값 변경 |
| `consumer` | `consumer` | 동일 유지 |
| `mobility` | `mobility` | 동일 유지 |
| `bio` | `bio` | 동일 유지 |
| `energy` | `energy` | 동일 유지 |
| `finance` | `finance` | 동일 유지 |

> 앞으로 추가/변경 시 이 문서를 먼저 수정하고, DB/Qdrant/프런트 필터가 모두 같은 리스트를 참조하도록 조치해야 합니다.

