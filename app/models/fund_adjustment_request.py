from pydantic import BaseModel


class FundAdjustmentRequest(BaseModel):
    """Positive amounts deposit funds; negative amounts withdraw them."""

    amount: float
