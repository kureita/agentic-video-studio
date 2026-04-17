from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

class User(BaseModel):
    id: str = Field(alias="_id")
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Billing
    usd_balance: float = 0.0  # USD balance (new users receive signup credit)
    referral_code: str
    referred_by: Optional[str] = None
    
    class Config:
        populate_by_name = True
