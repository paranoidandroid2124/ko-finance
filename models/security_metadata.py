from sqlalchemy import BigInteger, Column, DateTime, JSON, Numeric, String, func

from database import Base


class SecurityMetadata(Base):
    """Reference data for KRX listings with latest market cap and bucket."""

    __tablename__ = "security_metadata"

    ticker = Column(String, primary_key=True)
    corp_code = Column(String, nullable=True, index=True)
    corp_name = Column(String, nullable=True)
    market = Column(String, nullable=True, index=True)
    shares = Column(BigInteger, nullable=True)
    market_cap = Column(Numeric, nullable=True)
    cap_bucket = Column(String, nullable=True, index=True)
    extra = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = ["SecurityMetadata"]
