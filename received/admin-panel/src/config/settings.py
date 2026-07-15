import os
import sys
import secrets
from dotenv import load_dotenv
from pathlib import Path

_dotenv_paths = [
    Path(__file__).resolve().parent.parent.parent / '.env',
    Path(sys.executable).parent / '.env' if getattr(sys, 'frozen', False) else None,
]
for p in filter(None, _dotenv_paths):
    if p.exists():
        load_dotenv(p)
        break
else:
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure bundled SSL certificates are found in frozen apps
try:
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
except Exception:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

_raw_secret = os.getenv("SECRET_KEY", "")
SECRET_KEY = _raw_secret if _raw_secret and _raw_secret != "change-this-in-production" else secrets.token_hex(32)

DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
HOST = os.getenv("FLASK_HOST", "127.0.0.1")
PORT = int(os.getenv("FLASK_PORT", "5001"))
