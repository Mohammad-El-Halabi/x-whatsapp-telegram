import json
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime


class Office(BaseModel):
    id: str
    name: str
    email: str
    password: Optional[str] = None
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class User(BaseModel):
    id: str
    email: str
    full_name: str
    role: str = "staff"
    office_id: Optional[str] = None
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StaffAssignment(BaseModel):
    id: Optional[str] = None
    user_id: str
    platform: str
    phone_number: str
    gateway_number: str
    account_slot: Optional[int] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = True
    connection_status: Optional[str] = "disconnected"
    connection_data: Optional[Any] = None
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
                return v
        return v


class ClientSecure(BaseModel):
    id: Optional[str] = None
    masked_identity: str
    real_identifier: str
    office_id: Optional[str] = None
    gateway_number: str = "default"
    platforms: List[str] = Field(default_factory=list)
    platform_identifiers: dict = Field(default_factory=dict)
    staff_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
