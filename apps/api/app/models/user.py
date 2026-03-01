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
    credits_balance: int = 1000
    referral_code: str
    referred_by: Optional[str] = None
    
    class Config:
        populate_by_name = True
