import os
import sys
from dotenv import load_dotenv
from pathlib import Path


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).resolve().parent.parent.parent


APP_DIR = _app_dir()

# Ensure bundled SSL certificates are found in frozen apps
try:
    import certifi
    os.environ.setdefault('SSL_CERT_FILE', certifi.where())
    os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
except Exception:
    pass

SESSION_DIR = APP_DIR / "session"
SESSION_DIR.mkdir(exist_ok=True)

ENV_PATH = APP_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing Configuration",
        f"Missing Supabase configuration.\n\n"
        f"Please ensure a .env file exists at:\n{ENV_PATH}\n\n"
        f"Required variables:\n"
        f"  SUPABASE_URL\n"
        f"  SUPABASE_KEY\n"
        f"  SUPABASE_SERVICE_KEY"
    )
    root.destroy()
    sys.exit(1)

SIGNAL_CLI_PATH = os.getenv("SIGNAL_CLI_PATH", str(APP_DIR / "signal-cli" / "bin" / "signal-cli.bat"))
if SIGNAL_CLI_PATH and not Path(SIGNAL_CLI_PATH).is_absolute():
    SIGNAL_CLI_PATH = str(APP_DIR / SIGNAL_CLI_PATH)
JAVA_HOME = os.getenv("JAVA_HOME", "")
if JAVA_HOME and not Path(JAVA_HOME).is_absolute():
    JAVA_HOME = str(APP_DIR / JAVA_HOME)

ACCOUNTS_FILE = SESSION_DIR / "accounts.json"
