import asyncio
import subprocess
import logging
import os
import json
import threading
from typing import Optional, Callable, List
from src.config.settings import SIGNAL_CLI_PATH, SESSION_DIR, JAVA_HOME, ACCOUNTS_FILE

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SignalService:
    def __init__(self, number: str = ""):
        self.cli_path = SIGNAL_CLI_PATH
        self.number = number
        self.session_dir = str(SESSION_DIR)
        self.is_connected = False
        self._process: Optional[subprocess.Popen] = None
        self._daemon_port: int = 0
        self._callbacks = {"on_message": [], "on_receipt": [], "on_call": [], "on_typing": [], "on_reaction": []}
        self._receive_task: Optional[asyncio.Task] = None
        self._call_id: Optional[str] = None
        self._suspend_receive = False  # set True during voice call to avoid config lock conflicts
        self._cli_lock = threading.Lock()  # serializes concurrent signal-cli calls (file lock contention)

    def _make_env(self) -> dict:
        env = os.environ.copy()
        if JAVA_HOME:
            env["JAVA_HOME"] = JAVA_HOME
        # Point signal-cli to our Python-based WebRTC tunnel binary for voice calls
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
        tunnel_bin = os.path.join(scripts_dir, "signal-call-tunnel.bat")
        if os.path.exists(tunnel_bin):
            env["SIGNAL_CALL_TUNNEL_BIN"] = tunnel_bin
        return env

    # --- CLI helpers ---

    def _run(self, args: list, timeout: int = 30) -> tuple[str, str, int]:
        cmd = [self.cli_path] + args
        logger.debug(f"_run: {' '.join(cmd)} (timeout={timeout}s)")
        with self._cli_lock:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=timeout,
                    cwd=self.session_dir, env=self._make_env()
                )
                stdout = result.stdout.decode('utf-8', errors='replace').strip() if result.stdout else ""
                stderr = result.stderr.decode('utf-8', errors='replace').strip() if result.stderr else ""
                logger.debug(f"_run: rc={result.returncode}, out_len={len(stdout)}, err_len={len(stderr)}")
                return stdout, stderr, result.returncode
            except subprocess.TimeoutExpired:
                logger.debug(f"_run: TIMEOUT after {timeout}s")
                return "", "timeout", -1
            except FileNotFoundError:
                logger.debug(f"_run: signal-cli not found at {self.cli_path}")
                return "", "signal-cli not found", -1
            except Exception as e:
                logger.debug(f"_run: ERROR: {e}")
                return "", str(e), -1

    async def _run_async(self, args: list, timeout: int = 30) -> tuple[str, str, int]:
        return await asyncio.to_thread(self._run, args, timeout)

    # --- Persistence ---

    @staticmethod
    def save_account(number: str):
        data = {"numbers": []}
        if ACCOUNTS_FILE.exists():
            try:
                data = json.loads(ACCOUNTS_FILE.read_text())
            except Exception:
                pass
        if number not in data["numbers"]:
            data["numbers"].append(number)
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACCOUNTS_FILE.write_text(json.dumps(data, indent=2))

    @staticmethod
    def load_accounts() -> list[str]:
        if ACCOUNTS_FILE.exists():
            try:
                data = json.loads(ACCOUNTS_FILE.read_text())
                return data.get("numbers", [])
            except Exception:
                pass
        return []

    @staticmethod
    def remove_account(number: str):
        if ACCOUNTS_FILE.exists():
            try:
                data = json.loads(ACCOUNTS_FILE.read_text())
                data["numbers"] = [n for n in data["numbers"] if n != number]
                ACCOUNTS_FILE.write_text(json.dumps(data, indent=2))
            except Exception:
                pass

    # --- Detection ---

    async def check_installed(self) -> bool:
        out, err, rc = await self._run_async(["--version"])
        return rc == 0

    async def get_version(self) -> str:
        out, err, rc = await self._run_async(["--version"])
        return out if rc == 0 else err

    # --- Linking ---

    async def link_device(self) -> Optional[str]:
        cmd = [self.cli_path, "link", "-n", "Signal Staff App"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=self.session_dir, env=self._make_env()
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                out = stdout.decode().strip()
                if out:
                    return out
                logger.error(f"Link failed: {stderr.decode()}")
                return None
            except asyncio.TimeoutError:
                proc.kill()
                return None
        except FileNotFoundError:
            return None

    async def wait_for_linked_number(self) -> Optional[str]:
        for _ in range(30):
            out, err, rc = await self._run_async(["-o", "json", "listAccounts"], timeout=10)
            if rc == 0 and out.strip():
                try:
                    data = json.loads(out)
                    if isinstance(data, list):
                        for entry in data:
                            num = entry.get("number", "")
                            if num.startswith("+"):
                                return num
                    elif isinstance(data, dict):
                        num = data.get("number", "")
                        if num.startswith("+"):
                            return num
                except json.JSONDecodeError:
                    pass
            await asyncio.sleep(2)
        return None

    # --- Registration ---

    async def register_number(self, phone: str, use_voice: bool = False, captcha: str = "") -> tuple[bool, str]:
        if not phone.startswith("+"):
            phone = "+" + phone
        args = ["-u", phone, "register"]
        if use_voice:
            args.append("--voice")
        if captcha:
            args.extend(["--captcha", captcha])
        out, err, rc = await self._run_async(args, timeout=120)
        if rc != 0:
            return False, err.strip()
        return True, ""

    async def verify_number(self, phone: str, code: str) -> tuple[bool, str]:
        if not phone.startswith("+"):
            phone = "+" + phone
        out, err, rc = await self._run_async(["-u", phone, "verify", code], timeout=30)
        if rc != 0:
            return False, err.strip()
        return True, ""

    # --- Daemon (persistent connection) ---

    async def start_daemon(self) -> bool:
        logger.debug(f"start_daemon: number='{self.number}'")
        if self._process and self._process.poll() is None:
            logger.debug("start_daemon: already running")
            return True
        try:
            port = self._find_free_port(17582)
            logger.debug(f"start_daemon: using port {port}")
            self._process = subprocess.Popen(
                [self.cli_path, "-u", self.number, "daemon",
                 "--json-rpc-tcp", f"127.0.0.1:{port}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                cwd=self.session_dir, env=self._make_env()
            )
            for _ in range(5):
                if self._process.poll() is not None:
                    logger.debug(f"start_daemon: exited immediately")
                    self._process = None
                    return False
                await asyncio.sleep(1)
            if self._process and self._process.poll() is None:
                logger.debug(f"start_daemon: running on port {port}")
                self._daemon_port = port
                return True
            logger.debug(f"start_daemon: failed to start")
            return False
        except Exception as e:
            logger.debug(f"start_daemon: ERROR: {e}")
            return False

    def _find_free_port(self, start: int) -> int:
        import socket
        for port in range(start, start + 100):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        return start

    async def stop_daemon(self):
        logger.debug(f"stop_daemon: number='{self.number}'")
        if self._process:
            logger.debug("stop_daemon: terminating")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            logger.debug("stop_daemon: stopped")
        else:
            logger.debug("stop_daemon: no process")

    # --- Messaging ---

    async def send_message(self, recipient: str, message: str) -> bool:
        logger.debug(f"send_message: to='{recipient}', msg_len={len(message)}")
        if not self.number:
            logger.debug("send_message: no number set")
            return False
        cmd = ["-u", self.number, "send", "-m", message, recipient]
        out, err, rc = await self._run_async(cmd, timeout=30)
        logger.debug(f"send_message: rc={rc}, err='{err[:100]}'")
        return rc == 0

    async def send_file(self, recipient: str, filepath: str, message: str = "") -> bool:
        logger.debug(f"send_file: to='{recipient}', file='{filepath}', msg={bool(message)}")
        if not self.number or not os.path.exists(filepath):
            logger.debug(f"send_file: invalid number or file missing")
            return False
        cmd = ["-u", self.number, "send", "-a", filepath, recipient]
        if message:
            cmd.insert(-1, "-m")
            cmd.insert(-1, message)
        out, err, rc = await self._run_async(cmd, timeout=60)
        logger.debug(f"send_file: rc={rc}, err='{err[:100]}'")
        return rc == 0

    async def download_attachment(self, attachment_id: str, sender: str = "") -> Optional[bytes]:
        logger.debug(f"download_attachment: id='{attachment_id}', sender='{sender}'")
        if not self.number or not attachment_id:
            logger.debug("download_attachment: no number or empty id")
            return None
        cmd = [self.cli_path, "-u", self.number, "getAttachment"]
        cmd.extend(["--id", attachment_id])
        if sender:
            cmd.extend(["--recipient", sender])
        logger.debug(f"download_attachment: cmd={' '.join(cmd)}")
        return await asyncio.to_thread(self._download_attachment_sync, cmd)

    def _download_attachment_sync(self, cmd: list) -> Optional[bytes]:
        with self._cli_lock:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=30,
                    cwd=self.session_dir, env=self._make_env()
                )
                if result.returncode == 0 and result.stdout:
                    raw = result.stdout.strip()
                    logger.debug(f"download_attachment: success, {len(raw)} raw bytes")
                    import base64
                    try:
                        decoded = base64.b64decode(raw)
                        logger.debug(f"download_attachment: decoded to {len(decoded)} bytes")
                        return decoded
                    except Exception as b64e:
                        logger.debug(f"download_attachment: base64 decode failed: {b64e}, returning raw")
                        return raw
                err_text = result.stderr.decode() if result.stderr else ""
                logger.debug(f"download_attachment: FAILED rc={result.returncode}, err='{err_text[:200]}'")
                return None
            except subprocess.TimeoutExpired:
                logger.debug(f"download_attachment: TIMEOUT")
                return None
            except Exception as e:
                logger.error(f"download_attachment error: {e}")
                return None

    async def receive_messages(self) -> List[dict]:

        if not self.number:
            return []
        logger.info(f"receive_messages: running signal-cli -u {self.number} -o json receive -t 3")
        out, err, rc = await self._run_async(["-u", self.number, "-o", "json", "receive", "-t", "3"], timeout=15)
        logger.info(f"receive_messages (for {self.number}): rc={rc}, out='{out[:500] if out else ''}', err='{err[:200] if err else ''}'")
        if rc != 0 or not out:
            return []
        result = self._parse_json_output(out)
        logger.info(f"receive_messages: returning {len(result)} messages")
        return result

    def _parse_json_output(self, output: str) -> List[dict]:
        messages = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                env = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(env, dict):
                continue
            msg = {"source": self.number}
            # Extract sender
            if "envelope" in env:
                envelope = env["envelope"]
                if "sourceNumber" in envelope:
                    msg["sender_id"] = envelope["sourceNumber"]
                elif "source" in envelope:
                    msg["sender_id"] = envelope["source"]
                elif "sourceUuid" in envelope:
                    msg["sender_id"] = envelope["sourceUuid"]
                if "sourceDevice" in envelope:
                    msg["source_device"] = envelope["sourceDevice"]
                if "timestamp" in envelope:
                    msg["timestamp"] = str(envelope["timestamp"])
                # Extract data message
                if "dataMessage" in envelope:
                    data = envelope["dataMessage"]
                    if "message" in data:
                        msg["text"] = data["message"]
                    if "timestamp" in data:
                        msg["data_timestamp"] = str(data["timestamp"])
                    if "groupInfo" in data:
                        msg["group_id"] = data["groupInfo"].get("groupId", "")
                    if "attachments" in data and data["attachments"]:
                        msg["attachments"] = []
                        for att in data["attachments"]:
                            att_info = {
                                "id": str(att.get("id", "")),
                                "contentType": att.get("contentType", ""),
                                "size": att.get("size", 0),
                                "filename": att.get("filename", ""),
                            }
                            msg["attachments"].append(att_info)
                            if not msg.get("text") and att_info["contentType"].startswith("image/"):
                                msg["text"] = "🖼 Image"
                            elif not msg.get("text") and att_info["contentType"].startswith("audio/"):
                                msg["text"] = "🎤 Voice message"
                    self._parse_reactions(data, msg)
                # Extract sync message
                if "syncMessage" in envelope:
                    sync = envelope["syncMessage"]
                    if "sentMessage" in sync:
                        sent = sync["sentMessage"]
                        msg["is_sync"] = True
                        if "message" in sent:
                            msg["text"] = sent["message"]
                        if "destinationUuid" in sent:
                            msg["sender_id"] = sent["destinationUuid"]
                        elif "destination" in sent:
                            msg["sender_id"] = sent["destination"]
                        if "timestamp" in sent:
                            msg["data_timestamp"] = str(sent["timestamp"])
                        if "attachments" in sent and sent["attachments"]:
                            msg["attachments"] = []
                            for att in sent["attachments"]:
                                att_info = {
                                    "id": str(att.get("id", "")),
                                    "contentType": att.get("contentType", ""),
                                    "size": att.get("size", 0),
                                    "filename": att.get("filename", ""),
                                }
                                msg["attachments"].append(att_info)
                        self._parse_reactions(sent, msg)
                # Extract typing indicator
                self._parse_typing(envelope, msg)
                # Extract receipt message
                if "receiptMessage" in envelope:
                    receipt = envelope["receiptMessage"]
                    msg["receipt"] = {
                        "when": receipt.get("when", 0),
                        "isDelivery": receipt.get("isDelivery", False),
                        "isRead": receipt.get("isRead", False),
                        "isViewed": receipt.get("isViewed", False),
                        "timestamps": receipt.get("timestamps", [])
                    }
                # Extract call message
                if "callMessage" in envelope:
                    call = envelope["callMessage"]
                    call_type = call.get("type", "unknown")
                    call_id = str(call.get("callId", ""))
                    msg["call"] = {"type": call_type, "callId": call_id}
                    if call_type in ("OFFER", "ANSWER"):
                        msg["text"] = f"📞 {'Incoming' if call_type == 'OFFER' else 'Answered'} call"
                    elif call_type == "HANGUP":
                        msg["text"] = "📞 Call ended"
                    else:
                        msg["text"] = "📞 Missed call"
            if "text" in msg:
                messages.append(msg)
            elif "receipt" in msg:
                messages.append(msg)
            elif "call" in msg:
                messages.append(msg)
            elif "attachments" in msg:
                messages.append(msg)
            elif "reaction" in msg:
                messages.append(msg)
            elif "typing" in msg:
                messages.append(msg)
            elif msg.get("is_sync"):
                messages.append(msg)
        logger.info(f"_parse_json_output: returning {len(messages)} messages: {messages}")
        return messages

    def _parse_reactions(self, data: dict, msg: dict):
        """Extract reaction from a dataMessage or sync sentMessage."""
        reaction = data.get("reaction")
        if reaction:
            msg["reaction"] = {
                "emoji": reaction.get("emoji", ""),
                "target_author": reaction.get("targetAuthor", ""),
                "target_sent_timestamp": str(reaction.get("targetSentTimestamp", "")),
                "remove": reaction.get("remove", False),
            }

    def _parse_typing(self, envelope: dict, msg: dict):
        """Extract typing indicator from envelope."""
        typing = envelope.get("typing")
        if typing:
            msg["typing"] = {
                "action": typing.get("action", "STARTED"),
                "timestamp": str(typing.get("timestamp", "")),
            }

    # --- Contacts ---

    async def get_contacts(self) -> List[dict]:
        logger.debug(f"get_contacts: number='{self.number}'")
        out, err, rc = await self._run_async(["-u", self.number, "-o", "json", "listContacts"], timeout=15)
        logger.debug(f"get_contacts: rc={rc}, out_len={len(out)}, err='{err[:100]}'")
        if rc != 0 or not out:
            logger.debug("get_contacts: no output")
            return []
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            logger.debug(f"get_contacts: JSON parse error: {e}")
            return []
        if not isinstance(data, list):
            logger.debug(f"get_contacts: not a list, got {type(data)}")
            return []
        contacts = []
        for entry in data:
            number = entry.get("number", "")
            name = entry.get("name") or ""
            if not name:
                name = entry.get("givenName") or ""
            if not name:
                name = (entry.get("profile") or {}).get("givenName") or ""
            if not name:
                name = number
            if number:
                contacts.append({"number": number, "name": name})
        logger.debug(f"get_contacts: returning {len(contacts)} contacts")
        for c in contacts:
            logger.debug(f"  - {c['number']}: '{c['name']}'")
        return contacts

    async def get_groups(self) -> List[dict]:
        out, err, rc = await self._run_async(["-u", self.number, "-o", "json", "listGroups"], timeout=15)
        if rc != 0 or not out:
            return []
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        groups = []
        for entry in data:
            gid = entry.get("groupId", "")
            name = entry.get("name", "") or gid
            if gid:
                groups.append({"id": gid, "name": name})
        return groups

    # --- New signal-cli wrappers ---

    async def send_receipt(self, recipient: str, timestamps: List[str],
                           receipt_type: str = "read") -> bool:
        logger.debug(f"send_receipt: to='{recipient}', {len(timestamps)} ts, type={receipt_type}")
        if not self.number or not recipient or not timestamps:
            return False
        success = True
        for ts in timestamps:
            cmd = ["-u", self.number, "sendReceipt", recipient,
                   "--target-timestamp", ts, "--type", receipt_type]
            out, err, rc = await self._run_async(cmd, timeout=15)
            if rc != 0:
                logger.debug(f"send_receipt: failed for ts={ts}: {err[:100]}")
                success = False
        return success

    async def send_typing(self, recipient: str, stop: bool = False) -> bool:
        logger.debug(f"send_typing: to='{recipient}', stop={stop}")
        if not self.number or not recipient:
            return False
        cmd = ["-u", self.number, "sendTyping", recipient]
        if stop:
            cmd.append("--stop")
        out, err, rc = await self._run_async(cmd, timeout=15)
        logger.debug(f"send_typing: rc={rc}")
        return rc == 0

    async def send_reaction(self, recipient: str, timestamp: str,
                            emoji: str, remove: bool = False,
                            target_author: str = "") -> bool:
        logger.debug(f"send_reaction: to='{recipient}', ts={timestamp}, emoji='{emoji}', remove={remove}")
        if not self.number or not recipient or not timestamp:
            return False
        cmd = ["-u", self.number, "sendReaction", recipient,
               "--emoji", emoji, "--target-timestamp", timestamp]
        if target_author:
            cmd.extend(["--target-author", target_author])
        if remove:
            cmd.append("--remove")
        out, err, rc = await self._run_async(cmd, timeout=15)
        logger.debug(f"send_reaction: rc={rc}")
        return rc == 0

    async def update_contact(self, recipient: str, given_name: str = "",
                             family_name: str = "", nickname: str = "",
                             expiration: int = 0) -> bool:
        logger.debug(f"update_contact: to='{recipient}', name='{given_name}'")
        if not self.number or not recipient:
            return False
        cmd = ["-u", self.number, "updateContact"]
        if given_name:
            cmd.extend(["--name", given_name])
        if family_name:
            cmd.extend(["--family-name", family_name])
        if nickname:
            cmd.extend(["--nick-given-name", nickname])
        if expiration > 0:
            cmd.extend(["--expiration", str(expiration)])
        cmd.append(recipient)
        out, err, rc = await self._run_async(cmd, timeout=15)
        return rc == 0

    async def block_contact(self, recipient: str) -> bool:
        if not self.number or not recipient:
            return False
        out, err, rc = await self._run_async(
            ["-u", self.number, "block", recipient], timeout=15)
        return rc == 0

    async def unblock_contact(self, recipient: str) -> bool:
        if not self.number or not recipient:
            return False
        out, err, rc = await self._run_async(
            ["-u", self.number, "unblock", recipient], timeout=15)
        return rc == 0

    async def update_profile(self, given_name: str = "", about: str = "",
                             avatar: str = "") -> bool:
        logger.debug(f"update_profile: name='{given_name}'")
        if not self.number:
            return False
        cmd = ["-u", self.number, "updateAccount"]
        if given_name:
            cmd.extend(["--profile-name", given_name])
        if about:
            cmd.extend(["--about", about])
        if avatar:
            cmd.extend(["--avatar", avatar])
        out, err, rc = await self._run_async(cmd, timeout=15)
        return rc == 0

    async def update_configuration(self, read_receipts: bool = None,
                                   typing_indicators: bool = None) -> bool:
        logger.debug(f"update_configuration: read_receipts={read_receipts}, typing={typing_indicators}")
        if not self.number:
            return False
        cmd = ["-u", self.number, "updateConfiguration"]
        if read_receipts is not None:
            cmd.extend(["--read-receipts", "true" if read_receipts else "false"])
        if typing_indicators is not None:
            cmd.extend(["--typing-indicators", "true" if typing_indicators else "false"])
        out, err, rc = await self._run_async(cmd, timeout=15)
        return rc == 0

    async def get_profile(self, recipient: str) -> Optional[dict]:
        logger.debug(f"get_profile: to='{recipient}'")
        if not self.number or not recipient:
            return None
        out, err, rc = await self._run_async(
            ["-u", self.number, "-o", "json", "getProfile", recipient], timeout=15
        )
        if rc != 0 or not out:
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return None

    async def get_avatar(self, recipient: str) -> Optional[bytes]:
        logger.debug(f"get_avatar: to='{recipient}'")
        if not self.number or not recipient:
            return None
        cmd = [self.cli_path, "-u", self.number, "getAvatar", recipient]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=self.session_dir, env=self._make_env()
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0 and stdout:
                return stdout
            return None
        except Exception as e:
            logger.error(f"getAvatar error: {e}")
            return None

    async def get_user_status(self, recipients: List[str]) -> List[dict]:
        logger.debug(f"get_user_status: {len(recipients)} recipients")
        if not self.number or not recipients:
            return []
        out, err, rc = await self._run_async(
            ["-u", self.number, "-o", "json", "getUserStatus"] + recipients, timeout=15
        )
        if rc != 0 or not out:
            return []
        try:
            data = json.loads(out)
            return data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            return []

    # --- Receive loop (polling as fallback) ---

    async def _receive_loop(self):
        logger.info("_receive_loop started")
        while self.is_connected:
            if self._suspend_receive:
                await asyncio.sleep(1)
                continue
            try:
                messages = await self.receive_messages()
                logger.info(f"_receive_loop: got {len(messages)} messages")
                for msg in messages:
                    if "typing" in msg:
                        logger.info(f"_receive_loop: dispatching typing: {msg}")
                        for cb in self._callbacks.get("on_typing", []):
                            try:
                                cb(msg)
                            except Exception as e:
                                logger.info(f"_receive_loop typing error: {e}")
                        continue
                    if "reaction" in msg:
                        logger.info(f"_receive_loop: dispatching reaction: {msg}")
                        for cb in self._callbacks.get("on_reaction", []):
                            try:
                                cb(msg)
                            except Exception as e:
                                logger.info(f"_receive_loop reaction error: {e}")
                        continue
                    if "text" in msg or "attachments" in msg or "call" in msg:
                        logger.info(f"_receive_loop: dispatching msg: {msg}")
                        for cb in self._callbacks["on_message"]:
                            try:
                                cb(msg)
                            except Exception as e:
                                logger.info(f"_receive_loop callback error: {e}")
                    elif "receipt" in msg:
                        logger.info(f"_receive_loop: dispatching receipt: {msg}")
                        for cb in self._callbacks.get("on_receipt", []):
                            try:
                                cb(msg)
                            except Exception as e:
                                logger.info(f"_receive_loop receipt error: {e}")
            except Exception as e:
                logger.info(f"_receive_loop error: {e}")
            await asyncio.sleep(3)

    # --- Connect / Disconnect ---

    async def connect(self) -> bool:
        logger.debug(f"connect: number='{self.number}', is_connected={self.is_connected}")
        if self.is_connected:
            logger.debug("connect: already connected")
            return True
        self.is_connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.debug("connect: receive loop started")
        return True

    async def disconnect(self):
        logger.debug(f"disconnect: number='{self.number}'")
        self.is_connected = False
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        await self.stop_daemon()
        logger.debug("disconnect: done")

    def on(self, event: str, callback: Callable):
        if event in self._callbacks:
            self._callbacks[event].append(callback)
