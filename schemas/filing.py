from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class FilingUrls(BaseModel):
    pdf: Optional[str] = None
    xbrl: Optional[str] = None
    html: Optional[str] = None
    viewer: Optional[str] = None


class Chunk(BaseModel):
    type: str
    content: str
    page_number: Optional[int] = None


class Filing(BaseModel):
    """데이터 계약에 맞춘 Filing 도메인 모델"""

    id: str = Field(..., description="내부 생성 UUID")
    corp_code: Optional[str] = Field(None, description="DART 기업 고유번호")
    corp_name: Optional[str] = Field(None, description="기업명")
    ticker: Optional[str] = Field(None, description="종목 코드")
    market: Optional[str] = Field(None, description="시장 (KR, US 등)")

    title: Optional[str] = Field(None, description="원본 제목")
    report_name: Optional[str] = Field(None, description="정규화된 보고서명")
    report_code: Optional[str] = Field(None, description="DART 리포트 코드")
    receipt_no: Optional[str] = Field(None, description="DART 접수번호")
    filed_at: Optional[datetime] = Field(None, description="공시 제출일시")

    file_name: Optional[str] = Field(None, description="업로드된 파일명")
    file_path: Optional[str] = Field(None, description="저장 경로")
    urls: Optional[FilingUrls] = Field(None, description="공시 원문 URL 모음")
    source_files: Optional[Dict[str, Any]] = Field(None, description="원문 패키지 정보 (ZIP, XML, 첨부)")

    raw_md: Optional[str] = Field(None, description="정규화된 마크다운 원문")
    chunks: Optional[List[Chunk]] = Field(None, description="구조화된 청크 목록")

    status: str = Field("PENDING", description="전처리 상태")
    analysis_status: str = Field("PENDING", description="분석 파이프라인 상태")
    category: Optional[str] = Field(None, description="LLM 분류 결과")
    category_confidence: Optional[float] = Field(None, description="분류 신뢰도")
    notes: Optional[str] = Field(None, description="오류/메모")

    created_at: Optional[datetime] = Field(None, description="생성 일시")
    updated_at: Optional[datetime] = Field(None, description="갱신 일시")
