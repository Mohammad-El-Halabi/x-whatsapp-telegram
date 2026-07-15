from supabase import create_client, Client
from src.config.settings import SUPABASE_URL, SUPABASE_KEY, SESSION_DIR, ENV_PATH
from src.models.schemas import User, StaffAssignment, ClientSecure
from typing import Optional, List
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SupabaseService:
    SESSION_FILE = SESSION_DIR / "session.json"

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                f"Missing Supabase configuration. Create {ENV_PATH} "
                "with SUPABASE_URL and SUPABASE_ANON_KEY."
            )
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        # Set tighter timeouts on all HTTP sessions
        try:
            import httpx
            to = httpx.Timeout(10.0, connect=8.0)
            self.client.postgrest.session.timeout = to
        except Exception:
            pass

    def sign_in(self, email: str, password: str) -> Optional[User]:
        logger.debug(f" sign_in: email='{email}'")
        try:
            response = self.client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            if not response or not response.user:
                logger.debug("sign_in: no response or no user")
                return None
            self._access_token = response.session.access_token if response.session else None
            self._refresh_token = response.session.refresh_token if response.session else None
            user = response.user
            user_id = str(getattr(user, "id", ""))
            email_str = getattr(user, "email", email) or email
            logger.debug(f" sign_in: user_id='{user_id}', email='{email_str}'")
            profile = self.get_user_by_email(email_str)
            office_id = profile.office_id if profile else None
            logger.debug(f" sign_in: profile={'found' if profile else 'None'}, office_id='{office_id}'")
            if profile:
                logger.debug(f" sign_in: returning profile: id={profile.id}, office_id={profile.office_id}")
                return profile
            metadata = getattr(user, "user_metadata", {}) or {}
            if isinstance(metadata, dict):
                full_name = metadata.get("full_name", email_str.split("@")[0])
                role = metadata.get("role", "staff")
            else:
                full_name = getattr(metadata, "full_name", email_str.split("@")[0]) if metadata else email_str.split("@")[0]
                role = getattr(metadata, "role", "staff") if metadata else "staff"
            result = User(
                id=user_id,
                email=email_str,
                full_name=full_name or email_str.split("@")[0],
                role=role or "staff",
                office_id=office_id,
                is_active=True,
            )
            logger.debug(f" sign_in: returning User id={result.id}, office_id={result.office_id}, role={result.role}")
            return result
        except Exception as e:
            logger.debug(f" Sign in failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def sign_out(self):
        logger.debug("sign_out")
        self._access_token = None
        self._refresh_token = None
        try:
            self.client.auth.sign_out()
        except Exception:
            pass

    def save_session(self):
        if not self._access_token:
            return
        try:
            email = ""
            try:
                user = self.client.auth.get_user()
                email = getattr(user, "email", "") or ""
            except Exception:
                pass
            data = {"access_token": self._access_token,
                    "refresh_token": self._refresh_token or "",
                    "user_email": email}
            self.SESSION_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.debug(f"save_session error: {e}")

    def restore_session(self) -> Optional[User]:
        try:
            if not self.SESSION_FILE.exists():
                return None
            data = json.loads(self.SESSION_FILE.read_text())
            access_token = data.get("access_token", "")
            refresh_token = data.get("refresh_token", "")
            email = data.get("user_email", "")
            if not access_token or not email:
                return None
            self.client.auth.set_session(access_token, refresh_token)
            self._access_token = access_token
            self._refresh_token = refresh_token
            profile = self.get_user_by_email(email)
            return profile
        except Exception as e:
            logger.debug(f"restore_session error: {e}")
            self.clear_session()
            return None

    def clear_session(self):
        try:
            if self.SESSION_FILE.exists():
                self.SESSION_FILE.unlink()
        except Exception:
            pass
        self._access_token = None
        self._refresh_token = None

    def get_user_by_email(self, email: str) -> Optional[User]:
        logger.debug(f" get_user_by_email: email='{email}'")
        result = self.client.table("users").select("*").eq("email", email).execute()
        logger.debug(f" get_user_by_email: data={result.data}")
        if result.data:
            user = User(**result.data[0])
            logger.debug(f" get_user_by_email: found id={user.id}, office_id={user.office_id}")
            return user
        logger.debug("get_user_by_email: not found")
        return None

    def get_staff_assignments(self, user_id: str, platform: str = "signal") -> List[StaffAssignment]:
        logger.debug(f" get_staff_assignments: user_id='{user_id}', platform='{platform}'")
        result = (
            self.client.table("staff_assignments")
            .select("*")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .eq("is_active", True)
            .execute()
        )
        logger.debug(f" get_staff_assignments: {len(result.data)} rows")
        return [StaffAssignment(**a) for a in result.data]

    @staticmethod
    def _gateway_matches(client: ClientSecure, gateway_number: str = None) -> bool:
        configured = (client.gateway_number or "default").strip()
        return not gateway_number or not configured or configured.lower() == "default" or configured == gateway_number.strip()

    @staticmethod
    def _identifier_matches(client: ClientSecure, identifier: str, platform: str) -> bool:
        expected = client.identifier_for(platform)
        return expected.lstrip("+") == identifier.strip().lstrip("+")

    def get_clients_by_office(self, office_id: str, gateway_number: str = None) -> List[ClientSecure]:
        logger.debug(f" get_clients_by_office: office_id='{office_id}'")
        result = (
            self.client.table("clients_secure")
            .select("*")
            .eq("office_id", office_id)
            .contains("platforms", ["signal"])
            .order("masked_identity")
            .execute()
        )
        logger.debug(f" get_clients_by_office: {len(result.data)} clients")
        clients = [ClientSecure(**c) for c in result.data]
        return [c for c in clients if self._gateway_matches(c, gateway_number)]

    def get_client_by_real_id(self, real_identifier: str, gateway_number: str = None) -> Optional[ClientSecure]:
        logger.debug(f" get_client_by_real_id: real_identifier='{real_identifier}'")
        result = (
            self.client.table("clients_secure")
            .select("*")
            .contains("platforms", ["signal"])
            .execute()
        )
        for row in result.data:
            client = ClientSecure(**row)
            if self._gateway_matches(client, gateway_number) and self._identifier_matches(client, real_identifier, "signal"):
                logger.debug("get_client_by_real_id: approved Signal client found")
                return client
        logger.debug("get_client_by_real_id: not found")
        return None

    def update_assignment_status(self, assignment_id: str, status: str, connection_data: dict = None):
        update_data = {"connection_status": status}
        if connection_data:
            update_data["connection_data"] = json.dumps(connection_data)
        if status == "connected":
            update_data["last_connected_at"] = datetime.now(timezone.utc).isoformat()
        self.client.table("staff_assignments").update(update_data).eq("id", assignment_id).execute()
