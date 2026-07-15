from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


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
    platform: str = "sms"
    phone_number: str
    gateway_number: str
    display_name: Optional[str] = None
    is_active: bool = True
    connection_status: str = "disconnected"
    connection_data: Optional[dict] = None
    last_connected_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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

    def identifier_for(self, platform: str) -> str:
        value = self.platform_identifiers.get(platform, "") if self.platform_identifiers else ""
        return str(value or self.real_identifier).strip()
