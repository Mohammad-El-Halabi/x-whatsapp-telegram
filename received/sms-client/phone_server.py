"""
SMS Gateway Server - Run this on your Android phone via Termux.

Setup:
1. Install Termux from F-Droid (NOT Play Store)
2. In Termux run:
   pkg install python
   pkg install termux-api
3. Install "Termux:API" app from F-Droid
4. Run: python phone_server.py

This creates an HTTP server that your PC software connects to.
It can send SMS, receive SMS, make calls, and get phone info.
"""

import os
import json
import time
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 8080
INCOMING_SMS = []
INCOMING_CALLS = []
SMS_FILE = os.path.expanduser("~/.sms_gateway_incoming.json")
CALLS_FILE = os.path.expanduser("~/.sms_gateway_calls.json")


def load_data():
    global INCOMING_SMS, INCOMING_CALLS
    try:
        with open(SMS_FILE, "r") as f:
            INCOMING_SMS = json.load(f)
    except Exception:
        INCOMING_SMS = []
    try:
        with open(CALLS_FILE, "r") as f:
            INCOMING_CALLS = json.load(f)
    except Exception:
        INCOMING_CALLS = []


def save_data():
    try:
        with open(SMS_FILE, "w") as f:
            json.dump(INCOMING_SMS[-200:], f)
    except Exception:
        pass
    try:
        with open(CALLS_FILE, "w") as f:
            json.dump(INCOMING_CALLS[-100:], f)
    except Exception:
        pass


def run_command(cmd):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1


def watch_incoming_sms():
    try:
        proc = subprocess.Popen(
            ["termux-sms-receive"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        buffer = ""
        while True:
            char = proc.stdout.read(1)
            if not char:
                break
            buffer += char
            if char == "\n":
                line = buffer.strip()
                buffer = ""
                if line:
                    try:
                        data = json.loads(line)
                        entry = {
                            "phone": data.get("number", ""),
                            "message": data.get("message", ""),
                            "time": datetime.now().isoformat(),
                        }
                    except json.JSONDecodeError:
                        entry = {
                            "phone": "",
                            "message": line,
                            "time": datetime.now().isoformat(),
                        }
                    INCOMING_SMS.append(entry)
                    save_data()
                    print(f"[SMS] {entry['phone']}: {entry['message'][:50]}")
    except FileNotFoundError:
        print("[WARN] termux-sms-receive not found. Install: pkg install termux-api")
    except Exception as e:
        print(f"[ERROR] SMS watcher failed: {e}")


class SMSHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self._send_json(200, {})

    def do_GET(self):
        if self.path == "/" or self.path == "/status":
            phone_number = ""
            try:
                out, _ = run_command("termux-telephony-deviceinfo")
                info = json.loads(out)
                phone_number = info.get("line1Number", "")
            except Exception:
                pass

            battery = 0
            try:
                out, _ = run_command("termux-battery-status")
                info = json.loads(out)
                battery = info.get("percentage", 0)
            except Exception:
                pass

            signal = 0
            try:
                out, _ = run_command("termux-telephony-signalinfo")
                info = json.loads(out)
                signal = info.get("dbm", 0)
            except Exception:
                pass

            self._send_json(200, {
                "status": "running",
                "phone_number": phone_number,
                "battery": battery,
                "signal": signal,
                "sms_count": len(INCOMING_SMS),
                "calls_count": len(INCOMING_CALLS),
            })

        elif self.path == "/sms/inbox":
            self._send_json(200, {"messages": INCOMING_SMS[-50:]})

        elif self.path == "/sms/list":
            out, code = run_command("termux-sms-list -l 50")
            messages = []
            try:
                messages = json.loads(out) if out else []
            except Exception:
                pass
            self._send_json(200, {"messages": messages})

        elif self.path == "/calls/log":
            out, code = run_command("termux-call-log -l 50")
            calls = []
            try:
                calls = json.loads(out) if out else []
            except Exception:
                pass
            self._send_json(200, {"calls": calls})

        elif self.path == "/contacts/list":
            out, code = run_command("termux-contact-list")
            contacts = []
            try:
                contacts = json.loads(out) if out else []
            except Exception:
                pass
            self._send_json(200, {"contacts": contacts})

        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        try:
            data = json.loads(body)
        except Exception:
            self._send_json(400, {"error": "invalid json"})
            return

        if self.path == "/sms/send":
            phone = data.get("phone", "")
            message = data.get("message", "")
            if not phone or not message:
                self._send_json(400, {"error": "phone and message required"})
                return
            out, code = run_command(f'termux-sms-send -n "{phone}" "{message}"')
            self._send_json(200, {"status": "sent", "output": out})

        elif self.path == "/call/make":
            phone = data.get("phone", "")
            if not phone:
                self._send_json(400, {"error": "phone required"})
                return
            out, code = run_command(f'termux-telephony-call "{phone}"')
            self._send_json(200, {"status": "calling", "output": out})

        elif self.path == "/call/end":
            out, code = run_command("input keyevent KEYCODE_ENDCALL")
            self._send_json(200, {"status": "ended"})

        elif self.path == "/call/answer":
            out, code = run_command("input keyevent KEYCODE_CALL")
            self._send_json(200, {"status": "answered"})

        elif self.path == "/info/device":
            device_info = {}
            try:
                out, _ = run_command("termux-telephony-deviceinfo")
                device_info["telephony"] = json.loads(out)
            except Exception:
                pass
            try:
                out, _ = run_command("termux-battery-status")
                device_info["battery"] = json.loads(out)
            except Exception:
                pass
            try:
                out, _ = run_command("termux-wifi-connectioninfo")
                device_info["wifi"] = json.loads(out)
            except Exception:
                pass
            self._send_json(200, device_info)

        elif self.path == "/v1/sms":
            phone = data.get("phone", data.get("to", ""))
            message = data.get("message", data.get("text", ""))
            if not phone or not message:
                self._send_json(400, {"error": "phone and message required"})
                return
            out, code = run_command(f'termux-sms-send -n "{phone}" "{message}"')
            self._send_json(200, {"status": "sent"})

        else:
            self._send_json(404, {"error": "not found"})


def main():
    load_data()
    print("=" * 50)
    print("  SMS Gateway Server for PC Control")
    print("=" * 50)
    print()

    try:
        out, _ = run_command("termux-telephony-deviceinfo")
        info = json.loads(out)
        print(f"  Phone: {info.get('line1Number', 'Unknown')}")
    except Exception:
        print("  Phone: Unknown")

    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "unknown"

    print(f"  IP: {local_ip}:{PORT}")
    print()
    print("  Enter this URL in your PC software:")
    print(f"  http://{local_ip}:{PORT}")
    print()
    print("  Waiting for commands...")
    print("=" * 50)
    print()

    sms_thread = threading.Thread(target=watch_incoming_sms, daemon=True)
    sms_thread.start()

    server = HTTPServer(("0.0.0.0", PORT), SMSHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
