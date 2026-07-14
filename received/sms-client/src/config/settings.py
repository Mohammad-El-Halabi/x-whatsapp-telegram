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

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SERVICE_ROLE_KEY", "")

MODEM_PORT = os.getenv("MODEM_PORT", "COM3")
MODEM_BAUD = int(os.getenv("MODEM_BAUD", "115200"))
