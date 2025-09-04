from pydantic import BaseModel
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
    success_url: str | None = None
    return_url: str | None = None   
    cancel_url: str | None = None
    ui_mode: str = "hosted"