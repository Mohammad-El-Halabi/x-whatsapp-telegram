from supabase import create_client, Client
from src.config.settings import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
from src.models.schemas import User, StaffAssignment, ClientSecure
from typing import Optional, List
import json
from datetime import datetime, timezone


class SupabaseService:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.admin_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def login(self, email: str, password: str) -> Optional[User]:
        auth_response = self.client.auth.sign_in_with_password({"email": email, "password": password})
        if not auth_response.user:
            return None
        result = self.admin_client.table("users").select("*").eq("id", auth_response.user.id).execute()
        if result.data:
            return User(**result.data[0])
        return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        result = self.admin_client.table("users").select("*").eq("id", user_id).execute()
        if result.data:
            return User(**result.data[0])
        return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        result = self.admin_client.table("users").select("*").eq("email", email).execute()
        if result.data:
            return User(**result.data[0])
        return None

    def get_staff_assignments(self, user_id: str, platform: str = "sms") -> List[StaffAssignment]:
        result = (
            self.client.table("staff_assignments")
            .select("*")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .eq("is_active", True)
            .execute()
        )
        return [StaffAssignment(**a) for a in result.data]

    def get_client_by_real_id(self, real_identifier: str, gateway_number: str) -> Optional[ClientSecure]:
        result = (
            self.client.table("clients_secure")
            .select("*")
            .eq("real_identifier", real_identifier)
            .eq("gateway_number", gateway_number)
            .execute()
        )
        if result.data:
            return ClientSecure(**result.data[0])
        return None

    def get_clients_by_office(self, office_id: str) -> List[ClientSecure]:
        result = (
            self.admin_client.table("clients_secure")
            .select("*")
            .eq("office_id", office_id)
            .order("masked_identity")
            .execute()
        )
        return [ClientSecure(**c) for c in result.data]

    def get_all_clients(self) -> List[ClientSecure]:
        result = (
            self.admin_client.table("clients_secure")
            .select("*")
            .order("masked_identity")
            .execute()
        )
        return [ClientSecure(**c) for c in result.data]

    def update_assignment_status(self, assignment_id: str, status: str, connection_data: dict = None):
        update_data = {"connection_status": status}
        if connection_data:
            update_data["connection_data"] = json.dumps(connection_data)
        if status == "connected":
            update_data["last_connected_at"] = datetime.now(timezone.utc).isoformat()
        self.admin_client.table("staff_assignments").update(update_data).eq("id", assignment_id).execute()
