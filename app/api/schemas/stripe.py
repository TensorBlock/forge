from pydantic import BaseModel, field_validator
from typing import List, Literal

# https://docs.stripe.com/api/checkout/sessions/create
class StripeCheckoutSessionLineItemPriceDataProductData(BaseModel):
    name: str
    description: str | None = None
    images: List[str] | None = None

class StripeCheckoutSessionLineItemPriceData(BaseModel):
    currency: str
    product_data: StripeCheckoutSessionLineItemPriceDataProductData
    tax_behavior: str = "inclusive"
    unit_amount: int

class StripeCheckoutSessionLineItem(BaseModel):
    price_data: StripeCheckoutSessionLineItemPriceData
    quantity: int

class CreateCheckoutSessionRequest(BaseModel):
    line_items: List[StripeCheckoutSessionLineItem]
    # Only allow payment mode for now
    mode: Literal["payment"] = "payment"
    # Attach the session_id to the success_url
    # https://docs.stripe.com/payments/checkout/custom-success-page?payment-ui=stripe-hosted&utm_source=chatgpt.com#success-url
    success_url: str | None = None
    return_url: str | None = None   
    cancel_url: str | None = None
    ui_mode: str = "hosted"

    @field_validator("success_url")
    @classmethod
    def append_session_id_to_success_url(cls, value: str):
        if value is None:
            return None
        return value.rstrip("/") + "?session_id={CHECKOUT_SESSION_ID}"