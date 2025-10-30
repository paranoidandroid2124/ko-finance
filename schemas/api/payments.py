"""Payment API schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TossPaymentsConfigResponse(BaseModel):
    clientKey: str = Field(..., description="Public client key used by the Toss Payments widget.")
    successUrl: Optional[str] = Field(
        default=None,
        description="Optional redirect URL for successful payments.",
    )
    failUrl: Optional[str] = Field(
        default=None,
        description="Optional redirect URL for failed payments.",
    )


class TossPaymentsConfirmRequest(BaseModel):
    paymentKey: str = Field(..., description="Payment key returned by the Toss Payments widget.")
    orderId: str = Field(..., description="Unique order identifier used when creating the payment.")
    amount: int = Field(..., ge=0, description="Amount to confirm for the payment.")


class TossPaymentsConfirmResponse(BaseModel):
    paymentKey: str = Field(..., description="Confirmed payment key.")
    orderId: str = Field(..., description="Order identifier tied to the payment.")
    approvedAt: Optional[str] = Field(default=None, description="Approval timestamp provided by Toss Payments.")
    raw: dict = Field(default_factory=dict, description="Raw response payload from Toss Payments.")

