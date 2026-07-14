import os
import sys
from dotenv import load_dotenv
from pathlib import Path

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
    load_dotenv(BASE_DIR / ".env")
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    load_dotenv(BASE_DIR / ".env")

# Ensure bundled SSL certificates are found in frozen apps
try:
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
except Exception:
    pass

SESSION_DIR = BASE_DIR / "session"
SESSION_DIR.mkdir(exist_ok=True)
AUTH_SESSION_FILE = SESSION_DIR / "auth.json"

_api_id_str = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_ID = int(_api_id_str) if _api_id_str.strip() else 0
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
