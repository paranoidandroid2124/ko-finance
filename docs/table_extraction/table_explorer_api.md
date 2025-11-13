## Table Explorer API (Draft v1)

### Entitlement
- 모든 엔드포인트는 `table.explorer` 엔타이틀먼트가 필요하며, 상세 표/다운로드(`/{id}`, `/export`)는 Pro/Enterprise 플랜에서만 허용됩니다.
- Free/Starter 플랜이거나 기능이 비활성화된 경우 `403 {"detail": {"code": "...", ...}}`가 반환됩니다.

### 1. `GET /api/v1/table-explorer/tables`
List normalised tables with optional filters.

| Query | Type | Description |
| --- | --- | --- |
| `tableType` | string | Restrict to `dividend`, `treasury`, `cb_bw`, `financials` (default: all). |
| `receiptNo` | string | Filter by a DART receipt number. |
| `ticker` | string | Filter by ticker. |
| `corpCode` | string | Filter by DART corp code. |
| `limit` | int | Page size (1~100, default 20). |
| `offset` | int | Cursor offset (default 0). |

**Response**
```jsonc
{
  "items": [
    {
      "id": "6a7e6c28-...",
      "filingId": "ab13-...",
      "receiptNo": "20251110000235",
      "corpCode": "00126380",
      "ticker": "005930",
      "tableType": "dividend",
      "tableTitle": "배당성향 요약",
      "pageNumber": 42,
      "tableIndex": 1,
      "rowCount": 12,
      "columnCount": 8,
      "headerRows": 2,
      "confidence": 0.94,
      "createdAt": "2025-11-13T02:44:34.192Z",
      "updatedAt": "2025-11-13T02:44:34.192Z",
      "quality": {
        "headerCoverage": 0.88,
        "nonEmptyRatio": 0.73,
        "numericRatio": 0.66,
        "accuracyScore": 0.79
      }
    }
  ],
  "total": 12
}
```

### 2. `GET /api/v1/table-explorer/tables/{table_id}`
Fetch granular metadata plus cell-level payloads.

**Response**
```jsonc
{
  "id": "6a7e6c28-...",
  "filingId": "ab13-...",
  "receiptNo": "20251110000235",
  "corpCode": "00126380",
  "ticker": "005930",
  "tableType": "dividend",
  "tableTitle": "배당성향 요약",
  "pageNumber": 42,
  "tableIndex": 1,
  "rowCount": 12,
  "columnCount": 8,
  "headerRows": 2,
  "confidence": 0.94,
  "createdAt": "2025-11-13T02:44:34.192Z",
  "updatedAt": "2025-11-13T02:44:34.192Z",
  "quality": { ... },
  "columnHeaders": [
    ["배당", "구분"],
    ["배당", "구분상세"],
    ["2024", "1분기"],
    ["2024", "2분기"]
  ],
  "tableJson": {
    "headerRows": [...],
    "bodyRows": [...],
    "headerPaths": [...],
    "bbox": [51.0, 114.5, 545.2, 322.1],
    "metrics": { ... }
  },
  "cells": [
    {
      "rowIndex": 0,
      "columnIndex": 0,
      "headerPath": ["배당", "구분"],
      "value": "보통주",
      "normalizedValue": "보통주",
      "numericValue": null,
      "valueType": "text",
      "confidence": 0.75
    },
    {
      "rowIndex": 0,
      "columnIndex": 3,
      "headerPath": ["2024", "1분기"],
      "value": "1,000",
      "normalizedValue": "1,000",
      "numericValue": 1000.0,
      "valueType": "number",
      "confidence": 0.95
    }
  ]
}
```

### 3. `GET /api/v1/table-explorer/export`
Download the normalized table as CSV/JSON.

| Query | Type | Description |
| --- | --- | --- |
| `id` | UUID | Table identifier (same as `/tables/{id}`). |
| `fmt` | enum | `csv` (default) or `json`. |

CSV 응답은 `Content-Disposition: attachment` 헤더로 파일 다운로드가 가능하며, JSON 모드는 `tableJson` 구조를 그대로 반환합니다.

### 4. Error handling
| Status | Scenario |
| --- | --- |
| `403` | Missing `table.explorer` entitlement or insufficient plan tier. |
| `404` | Unknown `table_id`. |
| `422` | Invalid UUID / query parameter. |

### 5. Related configuration
- `.env`: `TABLE_EXTRACTION_*` knobs control the extractor (pages/tables/time budget + artefact output).
- `uploads/admin/plan_settings.json`: ensure the `table.explorer` entitlement is present for plans that can access these APIs.
- QA report: `reports/table_extraction/quality_report.json` tracks the latest 50-sample validation run (`scripts/table_extraction_eval.py`).
