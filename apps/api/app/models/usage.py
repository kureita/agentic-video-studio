from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

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

class ActionType(str, Enum):
    AI_CHAT = "ai_chat"
    VIDEO_GEN = "video_gen"
    IMAGE_GEN = "image_gen"
    AUDIO_GEN = "audio_gen"
    RENDER = "render"
    REFERRAL_BONUS = "referral_bonus"
    VOUCHER_REDEEM = "voucher_redeem"

class UsageLog(BaseModel):
    id: Optional[ObjectIdStr] = Field(alias="_id", default=None)
    user_id: str
    action_type: ActionType
    tokens_used: Optional[int] = None
    credits_deducted: int
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('id', mode='before')
    def parse_object_id(cls, v):
        if v is not None:
            return str(v)
        return v

    model_config = ConfigDict(populate_by_name=True)
