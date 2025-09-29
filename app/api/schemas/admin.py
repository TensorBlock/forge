from pydantic import BaseModel, field_validator

class AddBalanceRequest(BaseModel):
    user_id: int | None = None
    email: str | None = None
    amount: int # in cents

    @field_validator("amount")
    def validate_amount(cls, value: float):
        if value < 100:
            raise ValueError("Amount must be greater than 100 cents")
        return value
