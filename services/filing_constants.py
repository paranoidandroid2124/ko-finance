"""Constants for filing-related operations."""

from typing import Dict, List

# Report type mappings: Korean to internal codes
REPORT_TYPE_MAP: Dict[str, List[str]] = {
    "사업보고서": ["annual"],
    "반기보고서": ["semi_annual"],
    "분기보고서": ["quarterly"],
    "정기보고서": ["annual", "semi_annual", "quarterly"],
}

# Report type labels: Internal codes to Korean
REPORT_TYPE_LABELS: Dict[str, str] = {
    "annual": "사업보고서",
    "semi_annual": "반기보고서",
    "quarterly": "분기보고서",
}
