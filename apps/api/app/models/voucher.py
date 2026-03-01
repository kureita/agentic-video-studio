from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, field_validator

class ObjectIdStr(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ):
        from pydantic_core import core_schema
        return core_schema.union_schema([
            core_schema.str_schema(),
            core_schema.any_schema()
        ])

class Voucher(BaseModel):
    id: Optional[ObjectIdStr] = Field(alias="_id", default=None)
    code: str = Field(unique=True)
    credit_value: int
    is_redeemed: bool = False
    redeemed_by: Optional[str] = None
    redeemed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator('id', mode='before')
    def parse_object_id(cls, v):
        if v is not None:
            return str(v)
        return v
    
    model_config = ConfigDict(populate_by_name=True)
