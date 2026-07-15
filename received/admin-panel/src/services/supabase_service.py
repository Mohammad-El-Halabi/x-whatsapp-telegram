from supabase import create_client, Client
from src.config.settings import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
from src.models.schemas import User, Office, StaffAssignment, ClientSecure
from typing import Optional, List
import json
from datetime import datetime, timezone
import uuid


class SupabaseService:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.admin_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def login_with_email(self, email: str, password: str) -> Optional[dict]:
        try:
            auth_response = self.client.auth.sign_in_with_password({"email": email, "password": password})
            return {"id": auth_response.user.id, "email": auth_response.user.email}
        except Exception:
            return None

    def sign_out(self):
        try:
            self.client.auth.sign_out()
        except Exception:
            pass

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        try:
            result = self.admin_client.table("users").select("*").eq("id", user_id).execute()
            return User(**result.data[0]) if result.data else None
        except Exception:
            return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        try:
            result = self.admin_client.table("users").select("*").eq("email", email).execute()
            return User(**result.data[0]) if result.data else None
        except Exception:
            return None

    def get_all_users(self) -> List[User]:
        try:
            result = self.admin_client.table("users").select("*").execute()
            return [User(**u) for u in result.data]
        except Exception:
            return []

    def get_users_by_office(self, office_id: str) -> List[User]:
        try:
            result = self.admin_client.table("users").select("*").eq("office_id", office_id).execute()
            return [User(**u) for u in result.data]
        except Exception:
            return []

    def create_user_with_auth(self, email: str, password: str, full_name: str, role: str = "staff", office_id: str = None) -> Optional[User]:
        try:
            try:
                auth_result = self.admin_client.auth.admin.create_user({
                    "email": email, "password": password, "email_confirm": True
                })
                user_id = auth_result.user.id
            except Exception:
                auth_result = self.client.auth.sign_up({"email": email, "password": password})
                user_id = auth_result.user.id
            data = {"id": user_id, "email": email, "full_name": full_name, "role": role, "is_active": True}
            if office_id:
                data["office_id"] = office_id
            result = self.admin_client.table("users").insert(data).execute()
            return User(**result.data[0])
        except Exception:
            return None

    def update_user(self, user_id: str, data: dict) -> bool:
        try:
            self.admin_client.table("users").update(data).eq("id", user_id).execute()
            return True
        except Exception:
            return False

    def delete_user(self, user_id: str) -> bool:
        try:
            self.admin_client.table("users").delete().eq("id", user_id).execute()
            return True
        except Exception:
            return False

    def update_user_password(self, user_id: str, password: str) -> bool:
        try:
            self.admin_client.auth.admin.update_user_by_id(user_id, {"password": password})
            return True
        except Exception:
            return False

    def get_all_assignments(self) -> List[StaffAssignment]:
        try:
            result = self.admin_client.table("staff_assignments").select("*").execute()
            return [StaffAssignment(**a) for a in result.data]
        except Exception:
            return []

    def get_assignment_by_id(self, assignment_id: str) -> Optional[StaffAssignment]:
        try:
            result = self.admin_client.table("staff_assignments").select("*").eq("id", assignment_id).execute()
            return StaffAssignment(**result.data[0]) if result.data else None
        except Exception:
            return None

    def create_assignment(self, data: dict) -> Optional[StaffAssignment]:
        try:
            if "id" not in data:
                data["id"] = str(uuid.uuid4())
            result = self.admin_client.table("staff_assignments").insert(data).execute()
            return StaffAssignment(**result.data[0])
        except Exception:
            return None

    def create_assignment_pair(self, data: dict) -> bool:
        """Create the Telegram and WhatsApp rows for one shared account slot atomically."""
        try:
            common = dict(data)
            rows = []
            for platform in ("telegram", "whatsapp"):
                row = dict(common)
                row["id"] = str(uuid.uuid4())
                row["platform"] = platform
                rows.append(row)
            result = self.admin_client.table("staff_assignments").insert(rows).execute()
            return len(result.data or []) == 2
        except Exception:
            return False

    def update_assignment(self, assignment_id: str, data: dict) -> bool:
        try:
            self.admin_client.table("staff_assignments").update(data).eq("id", assignment_id).execute()
            return True
        except Exception:
            return False

    def update_assignment_pair(self, assignment_id: str, data: dict) -> bool:
        """Keep both platforms in a numbered slot on the same phone and gateway."""
        try:
            assignment = self.get_assignment_by_id(assignment_id)
            if not assignment:
                return False
            if assignment.account_slot is None:
                return self.update_assignment(assignment_id, data)
            result = (
                self.admin_client.table("staff_assignments")
                .update(data)
                .eq("user_id", assignment.user_id)
                .eq("account_slot", assignment.account_slot)
                .execute()
            )
            return len(result.data or []) >= 1
        except Exception:
            return False

    def delete_assignment(self, assignment_id: str) -> bool:
        try:
            self.admin_client.table("staff_assignments").delete().eq("id", assignment_id).execute()
            return True
        except Exception:
            return False

    def delete_assignment_pair(self, assignment_id: str) -> bool:
        """Delete both platform rows for a numbered slot; preserve legacy row behavior."""
        try:
            assignment = self.get_assignment_by_id(assignment_id)
            if not assignment:
                return False
            query = self.admin_client.table("staff_assignments").delete().eq("user_id", assignment.user_id)
            if assignment.account_slot is None:
                query = query.eq("id", assignment_id)
            else:
                query = query.eq("account_slot", assignment.account_slot)
            query.execute()
            return True
        except Exception:
            return False

    def get_all_clients(self, office_id: str = None) -> List[ClientSecure]:
        try:
            query = self.admin_client.table("clients_secure").select("*")
            if office_id:
                query = query.eq("office_id", office_id)
            result = query.execute()
            return [ClientSecure(**c) for c in result.data]
        except Exception:
            return []

    def create_client(self, data: dict) -> Optional[ClientSecure]:
        try:
            result = self.admin_client.table("clients_secure").insert(data).execute()
            return ClientSecure(**result.data[0])
        except Exception:
            return None

    def update_client(self, client_id: str, data: dict) -> bool:
        try:
            self.admin_client.table("clients_secure").update(data).eq("id", client_id).execute()
            return True
        except Exception:
            return False

    def delete_client(self, client_id: str) -> bool:
        try:
            self.admin_client.table("clients_secure").delete().eq("id", client_id).execute()
            return True
        except Exception:
            return False

    def get_dashboard_stats(self, office_id: str = None) -> dict:
        try:
            users = self.get_all_users()
            assignments = self.get_all_assignments()
            clients = self.get_all_clients(office_id)
            if office_id:
                users = [u for u in users if u.office_id == office_id]
            return {
                "total_users": len(users),
                "active_users": len([u for u in users if u.is_active]),
                "total_assignments": len(assignments),
                "connected_assignments": len([a for a in assignments if a.connection_status == "connected"]),
                "total_clients": len(clients),
            }
        except Exception:
            return {
                "total_users": 0, "active_users": 0, "total_assignments": 0,
                "connected_assignments": 0, "total_clients": 0,
            }

    # ---- Office CRUD ----

    def get_office_by_id(self, office_id: str) -> Optional[Office]:
        try:
            result = self.admin_client.table("offices").select("*").eq("id", office_id).execute()
            return Office(**result.data[0]) if result.data else None
        except Exception:
            return None

    def get_office_by_email(self, email: str) -> Optional[Office]:
        try:
            result = self.admin_client.table("offices").select("*").eq("email", email).execute()
            return Office(**result.data[0]) if result.data else None
        except Exception:
            return None

    def get_all_offices(self) -> List[Office]:
        try:
            result = self.admin_client.table("offices").select("*").execute()
            return [Office(**o) for o in result.data]
        except Exception:
            return []

    def create_office(self, data: dict) -> Optional[Office]:
        try:
            data["id"] = str(uuid.uuid4())
            result = self.admin_client.table("offices").insert(data).execute()
            return Office(**result.data[0])
        except Exception:
            return None

    def update_office(self, office_id: str, data: dict) -> bool:
        try:
            self.admin_client.table("offices").update(data).eq("id", office_id).execute()
            return True
        except Exception:
            return False

    def delete_office(self, office_id: str) -> bool:
        try:
            self.admin_client.table("offices").delete().eq("id", office_id).execute()
            return True
        except Exception:
            return False
