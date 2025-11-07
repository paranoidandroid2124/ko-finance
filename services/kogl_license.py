"""Helpers for detecting KOGL/open license metadata from feed entries."""

from __future__ import annotations

import re
from typing import Optional, Tuple

KOGL_TYPES = {
    "1": {
        "label": "KOGL 제1유형 (출처표시)",
        "url": "https://www.kogl.or.kr/info/licenseType1.do",
        "keywords": ("제1유형", "type1", "type 1", "출처표시"),
    },
    "2": {
        "label": "KOGL 제2유형 (출처표시-상업적 이용금지)",
        "url": "https://www.kogl.or.kr/info/licenseType2.do",
        "keywords": ("제2유형", "type2", "type 2", "상업적 이용금지"),
    },
    "3": {
        "label": "KOGL 제3유형 (출처표시-변경금지)",
        "url": "https://www.kogl.or.kr/info/licenseType3.do",
        "keywords": ("제3유형", "type3", "type 3", "변경금지"),
    },
    "4": {
        "label": "KOGL 제4유형 (출처표시-상업적 이용금지-변경금지)",
        "url": "https://www.kogl.or.kr/info/licenseType4.do",
        "keywords": ("제4유형", "type4", "type 4", "상업적 이용금지-변경금지"),
    },
}

_KOGL_URL_PATTERN = re.compile(r"licenseType([1-4])", re.IGNORECASE)


def detect_kogl_license(
    text: Optional[str],
    *,
    license_url: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to normalise KOGL license metadata from feed text/url.

    Returns
    -------
    Tuple[license_type, license_url]
    """

    if license_url:
        match = _KOGL_URL_PATTERN.search(license_url)
        if match:
            meta = KOGL_TYPES.get(match.group(1))
            if meta:
                return meta["label"], meta["url"]

    if text:
        lowered = text.lower()
        for code, meta in KOGL_TYPES.items():
            if any(keyword.lower() in lowered for keyword in meta["keywords"]):
                return meta["label"], meta["url"]

    return None, license_url


__all__ = ["detect_kogl_license"]
