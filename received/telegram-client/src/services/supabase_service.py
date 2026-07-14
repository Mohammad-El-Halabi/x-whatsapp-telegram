from supabase import create_client, Client
from src.config.settings import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
from src.models.schemas import User, StaffAssignment, ClientSecure
from typing import Optional, List
import json


class SupabaseService:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.admin_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def sign_in(self, email: str, password: str):
        result = self.client.auth.sign_in_with_password({"email": email, "password": password})
        return result

    def sign_out(self):
        self.client.auth.sign_out()

    def get_current_user(self):
        return self.client.auth.get_user()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        result = self.client.table("users").select("*").eq("id", user_id).execute()
        if result.data:
            return User(**result.data[0])
        return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        result = self.client.table("users").select("*").eq("email", email).execute()
        if result.data:
            return User(**result.data[0])
        return None

    def get_active_staff(self) -> List[User]:
        result = self.client.table("users").select("*").eq("is_active", True).execute()
        return [User(**u) for u in result.data]

    def get_staff_assignments(self, user_id: str, platform: str = "telegram") -> List[StaffAssignment]:
        result = (
            self.client.table("staff_assignments")
            .select("*")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .eq("is_active", True)
            .execute()
        )
        return [StaffAssignment(**a) for a in result.data]

    def get_assignment_by_gateway(self, gateway_number: str, platform: str = "telegram") -> Optional[StaffAssignment]:
        result = (
            self.client.table("staff_assignments")
            .select("*")
            .eq("gateway_number", gateway_number)
            .eq("platform", platform)
            .execute()
        )
        if result.data:
            return StaffAssignment(**result.data[0])
        return None

    def update_assignment_status(self, assignment_id: str, status: str, connection_data: dict = None):
        try:
            update_data = {"connection_status": status}
            if connection_data:
                update_data["connection_data"] = json.dumps(connection_data)
            if status == "connected":
                from datetime import datetime, timezone
                update_data["last_connected_at"] = datetime.now(timezone.utc).isoformat()
            self.admin_client.table("staff_assignments").update(update_data).eq("id", assignment_id).execute()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Status update failed for {assignment_id}: {e}")

    def get_clients_by_office(self, office_id: str, gateway_number: str) -> List[ClientSecure]:
        result = (
            self.admin_client.table("clients_secure")
            .select("*")
            .eq("office_id", office_id)
            .eq("gateway_number", gateway_number)
            .execute()
        )
        out = []
        for c in result.data:
            if isinstance(c.get("platform_identifiers"), str):
                try:
                    c["platform_identifiers"] = json.loads(c["platform_identifiers"])
                except (json.JSONDecodeError, TypeError):
                    c["platform_identifiers"] = {}
            out.append(ClientSecure(**c))
        return out

    def get_client_by_real_id(self, real_identifier: str, gateway_number: str) -> Optional[ClientSecure]:
        result = (
            self.admin_client.table("clients_secure")
            .select("*")
            .eq("real_identifier", real_identifier)
            .eq("gateway_number", gateway_number)
            .execute()
        )
        if result.data:
            return ClientSecure(**result.data[0])
        return None

    def create_client(self, client_data: dict) -> ClientSecure:
        result = self.admin_client.table("clients_secure").insert(client_data).execute()
        return ClientSecure(**result.data[0])

    def update_client(self, client_id: str, update_data: dict):
        self.admin_client.table("clients_secure").update(update_data).eq("id", client_id).execute()

    def get_all_active_assignments(self) -> List[StaffAssignment]:
        result = (
            self.client.table("staff_assignments")
            .select("*")
            .eq("platform", "telegram")
            .eq("is_active", True)
            .execute()
        )
        return [StaffAssignment(**a) for a in result.data]
