from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
import json


class User(BaseModel):
    id: str
    email: str
    full_name: str
    role: str = "staff"
    office_id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StaffAssignment(BaseModel):
    id: Optional[str] = None
    user_id: str
    platform: str = "telegram"
    phone_number: str
    gateway_number: str
    display_name: Optional[str] = None
    is_active: bool = True
    connection_status: str = "disconnected"
    connection_data: Optional[dict] = None
    last_connected_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("connection_data", mode="before")
    @classmethod
    def parse_connection_data(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class ClientSecure(BaseModel):
    id: Optional[str] = None
    masked_identity: str
    real_identifier: str
    platforms: List[str] = []
    platform_identifiers: dict = {}
    gateway_number: str = "default"
    staff_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Message(BaseModel):
    id: Optional[int] = None
    chat_id: int
    sender_id: int
    text: Optional[str] = None
    date: Optional[datetime] = None
    is_outgoing: bool = False
    is_read: bool = False


class CallInfo(BaseModel):
    id: Optional[int] = None
    user_id: int
    is_outgoing: bool = False
    is_video: bool = False
    status: str = "ringing"
    duration: int = 0
