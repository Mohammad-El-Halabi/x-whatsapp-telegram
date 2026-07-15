from supabase import create_client, Client
from src.config.settings import SUPABASE_URL, SUPABASE_KEY, ENV_PATH
from src.models.schemas import User, StaffAssignment, ClientSecure
from typing import Optional, List
import json
from datetime import datetime, timezone


class SupabaseService:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                f"Missing Supabase configuration. Create {ENV_PATH} "
                "with SUPABASE_URL and SUPABASE_ANON_KEY."
            )
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def login(self, email: str, password: str) -> Optional[User]:
        auth_response = self.client.auth.sign_in_with_password({"email": email, "password": password})
        if not auth_response.user:
            return None
        result = self.client.table("users").select("*").eq("id", auth_response.user.id).execute()
        if result.data:
            return User(**result.data[0])
        return None

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

    @staticmethod
    def _gateway_matches(client: ClientSecure, gateway_number: str = None) -> bool:
        configured = (client.gateway_number or "default").strip()
        return not gateway_number or not configured or configured.lower() == "default" or configured == gateway_number.strip()

    def get_client_by_real_id(self, real_identifier: str, gateway_number: str) -> Optional[ClientSecure]:
        result = (
            self.client.table("clients_secure")
            .select("*")
            .contains("platforms", ["sms"])
            .execute()
        )
        for row in result.data:
            client = ClientSecure(**row)
            if (
                self._gateway_matches(client, gateway_number)
                and client.identifier_for("sms").lstrip("+") == real_identifier.strip().lstrip("+")
            ):
                return client
        return None

    def get_clients_by_office(self, office_id: str, gateway_number: str = None) -> List[ClientSecure]:
        result = (
            self.client.table("clients_secure")
            .select("*")
            .eq("office_id", office_id)
            .contains("platforms", ["sms"])
            .order("masked_identity")
            .execute()
        )
        clients = [ClientSecure(**c) for c in result.data]
        return [c for c in clients if self._gateway_matches(c, gateway_number)]

    def get_all_clients(self) -> List[ClientSecure]:
        result = (
            self.client.table("clients_secure")
            .select("*")
            .contains("platforms", ["sms"])
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
        self.client.table("staff_assignments").update(update_data).eq("id", assignment_id).execute()
