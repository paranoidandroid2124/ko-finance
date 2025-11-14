"""Payment API schemas."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field

from core.plan_constants import PlanTier


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
    planTier: Optional[PlanTier] = Field(
        default=None,
        description="Optional plan tier being purchased; used when metadata is missing.",
    )


class TossPaymentsConfirmResponse(BaseModel):
    paymentKey: str = Field(..., description="Confirmed payment key.")
    orderId: str = Field(..., description="Order identifier tied to the payment.")
    approvedAt: Optional[str] = Field(default=None, description="Approval timestamp provided by Toss Payments.")
    raw: dict = Field(default_factory=dict, description="Raw response payload from Toss Payments.")


class TossCheckoutCreateRequest(BaseModel):
    planTier: PlanTier = Field(..., description="Target plan tier for the checkout.")
    amount: Optional[int] = Field(default=None, ge=0, description="Optional override for the checkout amount.")
    currency: Optional[str] = Field(default="KRW", description="Currency code (default KRW).")
    orderName: Optional[str] = Field(default=None, description="Custom order name shown on the checkout.")
    redirectPath: Optional[str] = Field(
        default=None,
        description="Relative path to return the user to after completing checkout.",
    )
    customerName: Optional[str] = Field(default=None, description="Optional customer name sent to Toss.")
    customerEmail: Optional[str] = Field(default=None, description="Optional customer email sent to Toss.")


class TossCheckoutCreateResponse(BaseModel):
    orderId: str
    planTier: PlanTier
    amount: int
    currency: str
    orderName: str
    successPath: str
    failPath: str
    status: str
    createdAt: str


class TossOrderStatusResponse(BaseModel):
    orderId: str
    planTier: PlanTier
    amount: int
    currency: str
    orderName: str
    status: str
    createdAt: str
    updatedAt: str
    metadata: Dict[str, object] = Field(default_factory=dict, description="Additional checkout metadata.")
