import asyncio
from telethon import TelegramClient, events, functions, types
from telethon.tl.types import (
    UserStatusOnline, UserStatusOffline, UserStatusRecently,
    UserStatusLastWeek, UserStatusLastMonth,
    InputPhoneCall, PhoneCallDiscardReasonMissed,
    UpdateNewChannelMessage, UpdateNewMessage,
    MessageMediaContact, MessageMediaPhoto,
    MessageMediaDocument
)
from telethon.errors import (
    AuthKeyUnregisteredError, FloodWaitError,
    CallAlreadyAcceptedError, CallAlreadyDeclinedError,
    SessionPasswordNeededError
)
from src.config.settings import TELEGRAM_API_ID, TELEGRAM_API_HASH, SESSION_DIR
from src.services.supabase_service import SupabaseService
from src.models.schemas import StaffAssignment, ClientSecure
from typing import Optional, Callable, Dict, List
import logging
from datetime import datetime, timezone
import json
import os
import mimetypes

try:
    from pytgcalls import PyTgCalls, MediaDevices
    from pytgcalls.types import CallConfig, ChatUpdate
    import ntgcalls
    _HAS_PYTGCALLS = True
except ImportError:
    _HAS_PYTGCALLS = False

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = str(SESSION_DIR.parent / "downloads")


class TelegramService:
    _PING_INTERVAL = 60

    def __init__(self, assignment: StaffAssignment):
        self.assignment = assignment
        self.supabase = SupabaseService()
        self.api_id = TELEGRAM_API_ID
        self.api_hash = TELEGRAM_API_HASH
        self.session_path = str(SESSION_DIR / f"tg_{assignment.id}")
        self.client: Optional[TelegramClient] = None
        self.is_connected = False
        self.current_call = None
        self._current_call_chat_id: Optional[int] = None
        self._pytgcalls: Optional[PyTgCalls] = None
        self._handlers_registered = False
        self._ping_task: Optional[asyncio.Task] = None
        self._callbacks = {
            "on_message": [],
            "on_call": [],
            "on_status_change": [],
            "on_read": [],
            "on_notification": [],
        }

    @property
    def has_session(self) -> bool:
        return os.path.exists(self.session_path + ".session")

    @property
    def download_dir(self) -> str:
        p = os.path.join(DOWNLOAD_DIR, str(self.assignment.id))
        os.makedirs(p, exist_ok=True)
        return p

    def _create_client(self):
        if not self.client:
            self.client = TelegramClient(
                self.session_path,
                self.api_id,
                self.api_hash
            )

    async def connect(self) -> bool:
        try:
            self._create_client()
            await self.client.start()
            if not await self.client.is_user_authorized():
                logger.warning("Client not authorized during connect")
                await self.client.disconnect()
                return False
            self.is_connected = True
            self._register_handlers()
            self._start_ping()
            await self._safe_update_status("connected", {})
            return True
        except Exception as e:
            logger.error(f"Connection failed for {self.assignment.gateway_number}: {e}")
            await self._safe_update_status("error", {"error": str(e)})
            return False

    async def _safe_update_status(self, status: str, data: dict = None):
        try:
            self.supabase.update_assignment_status(self.assignment.id, status, data)
        except Exception as e:
            logger.warning(f"Status update failed: {e}")

    def _start_ping(self):
        try:
            self._stop_ping()
            loop = asyncio.get_running_loop()
            self._ping_task = loop.create_task(self._ping_loop())
        except Exception:
            pass

    async def _ping_loop(self):
        while self.is_connected and self.client:
            try:
                await asyncio.sleep(self._PING_INTERVAL)
                if not self.is_connected or not self.client:
                    break
                me = await self.client.get_me()
                if me is None:
                    logger.warning("Ping failed - reconnecting")
                    await self._reconnect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Ping error: {e}")
                try:
                    await self._reconnect()
                except Exception:
                    pass

    def _stop_ping(self):
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None

    async def _reconnect(self):
        if self.is_connected:
            self.is_connected = False
            try:
                await self.client.disconnect()
            except Exception:
                pass
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Reconnect failed: {e}")
                await self._safe_update_status("error", {"error": str(e)})

    async def disconnect(self):
        self._stop_ping()
        await self._stop_pytgcalls()
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None
            self.is_connected = False
            self._handlers_registered = False
            await self._safe_update_status("disconnected")

    async def qr_login_flow(self, on_url: Callable = None, on_done: Callable = None):
        try:
            self._create_client()
            await self.client.connect()
            if await self.client.is_user_authorized():
                self.is_connected = True
                self._register_handlers()
                self.supabase.update_assignment_status(self.assignment.id, "connected", {})
                if on_done:
                    self._safe_call(on_done, True)
                return True
            qr_login = await self.client.qr_login()
            if on_url:
                self._safe_call(on_url, qr_login.url)
            await qr_login.wait()
            self.is_connected = True
            self._register_handlers()
            self.supabase.update_assignment_status(self.assignment.id, "connected", {})
            if on_done:
                self._safe_call(on_done, True)
            return True
        except Exception as e:
            logger.error(f"QR login failed: {e}")
            if on_done:
                self._safe_call(on_done, False)
            return False

    def _safe_call(self, cb: Callable, *args):
        try:
            cb(*args)
        except Exception:
            pass

    async def phone_request_code(self, phone: str) -> bool:
        try:
            self._create_client()
            await self.client.connect()
            if await self.client.is_user_authorized():
                self.is_connected = True
                self._register_handlers()
                self.supabase.update_assignment_status(self.assignment.id, "connected", {})
                return True
            await self.client.send_code_request(phone)
            self._current_phone = phone
            return True
        except Exception as e:
            logger.error(f"Send code failed: {e}")
            return False

    async def phone_submit_code(self, phone: str, code: str) -> str:
        try:
            await self.client.sign_in(phone, code)
            self.is_connected = True
            self._register_handlers()
            self.supabase.update_assignment_status(self.assignment.id, "connected", {})
            return "ok"
        except SessionPasswordNeededError:
            return "password_needed"
        except Exception as e:
            logger.error(f"Submit code failed: {e}")
            return "error"

    async def phone_submit_password(self, password: str) -> bool:
        try:
            await self.client.sign_in(password=password)
            self.is_connected = True
            self._register_handlers()
            self.supabase.update_assignment_status(self.assignment.id, "connected", {})
            return True
        except Exception as e:
            logger.error(f"Submit password failed: {e}")
            return False

    def _register_handlers(self):
        if not self.client or self._handlers_registered:
            return
        self._handlers_registered = True

        @self.client.on(events.NewMessage)
        async def handler_new_message(event):
            try:
                await self._handle_new_message(event)
            except Exception as e:
                logger.error(f"NewMessage handler error: {e}")

        @self.client.on(events.MessageRead)
        async def handler_message_read(event):
            try:
                await self._handle_message_read(event)
            except Exception as e:
                logger.error(f"MessageRead handler error: {e}")

        @self.client.on(events.UserUpdate)
        async def handler_user_update(event):
            try:
                await self._handle_user_status(event)
            except Exception as e:
                logger.error(f"UserUpdate handler error: {e}")

    def _extract_media_info(self, msg) -> Optional[dict]:
        if not msg.media:
            return None
        info = {}
        if isinstance(msg.media, MessageMediaPhoto):
            info["type"] = "photo"
            info["file_name"] = f"photo_{msg.id}.jpg"
            info["mime_type"] = "image/jpeg"
            if msg.media.photo:
                sizes = msg.media.photo.sizes
                if sizes:
                    last = sizes[-1]
                    info["width"] = getattr(last, "w", 0)
                    info["height"] = getattr(last, "h", 0)
        elif isinstance(msg.media, MessageMediaDocument):
            doc = msg.media.document
            info["mime_type"] = doc.mime_type or "application/octet-stream"
            info["file_size"] = doc.size
            for attr in doc.attributes:
                if isinstance(attr, types.DocumentAttributeVideo):
                    info["type"] = "video"
                    info["width"] = attr.w
                    info["height"] = attr.h
                    info["duration"] = attr.duration
                elif isinstance(attr, types.DocumentAttributeAudio):
                    if attr.voice:
                        info["type"] = "voice"
                    else:
                        info["type"] = "audio"
                    info["duration"] = attr.duration
                    info["file_name"] = getattr(attr, "file_name", None) or f"audio_{msg.id}.ogg"
                elif isinstance(attr, types.DocumentAttributeFilename):
                    info["file_name"] = attr.file_name
                elif isinstance(attr, types.DocumentAttributeSticker):
                    info["type"] = "sticker"
                    info["file_name"] = getattr(attr, "file_name", None) or f"sticker_{msg.id}.webp"
                    ss = getattr(attr, "stickerset", None)
                    if ss:
                        info["sticker_set"] = getattr(ss, "id", None)
            if "type" not in info:
                info["type"] = "document"
            if "file_name" not in info or not info["file_name"]:
                ext = mimetypes.guess_extension(info.get("mime_type", "")) or ""
                info["file_name"] = f"file_{msg.id}{ext}"
        else:
            info["type"] = "other"
            info["file_name"] = f"media_{msg.id}"
        return info

    async def download_media(self, msg) -> Optional[str]:
        if not msg.media or not self.client:
            return None
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            path = await self.client.download_media(msg, file=self.download_dir)
            return os.path.normpath(path) if path else None
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    async def _handle_new_message(self, event):
        if event.is_private:
            try:
                sender = await event.get_sender()
            except Exception:
                sender = None
            if sender is None:
                return
            is_out = event.message.out
            client = None
            if not is_out:
                client = self.supabase.get_client_by_real_id(
                    str(sender.id), self.assignment.gateway_number
                )

            media_info = self._extract_media_info(event.message)
            if media_info:
                asyncio.create_task(self._lazy_download_media(event.message, media_info))

            msg_data = {
                "id": event.message.id,
                "chat_id": event.chat_id,
                "sender_id": sender.id,
                "sender_name": getattr(sender, "first_name", "") or getattr(sender, "username", "") or "Unknown",
                "text": event.message.text or "",
                "date": event.message.date.isoformat(),
                "is_outgoing": is_out,
                "status": "sent" if is_out else None,
                "platform": "telegram",
                "gateway_number": self.assignment.gateway_number,
                "client_id": client.id if client else None,
                "media": media_info,
            }
            for cb in self._callbacks["on_message"]:
                try:
                    cb(msg_data)
                except Exception:
                    pass

    async def _lazy_download_media(self, msg, media_info: dict):
        try:
            path = await self.download_media(msg)
            if path:
                media_info["file_path"] = path
        except Exception as e:
            logger.debug(f"Lazy download failed: {e}")

    async def _handle_message_read(self, event):
        for cb in self._callbacks["on_read"]:
            cb({
                "chat_id": event.chat_id,
                "message_ids": event.message_ids,
                "is_read": True,
            })

    async def _handle_user_status(self, event):
        try:
            status = event.status
            status_text = "offline"
            if isinstance(status, UserStatusOnline):
                status_text = "online"
            elif isinstance(status, UserStatusOffline):
                status_text = "offline"
            elif isinstance(status, UserStatusRecently):
                status_text = "recently"
            for cb in self._callbacks["on_status_change"]:
                try:
                    cb({
                        "user_id": event.user_id,
                        "status": status_text,
                    })
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Status handler error: {e}")

    def _fire_call_event(self, data: dict):
        for cb in self._callbacks["on_call"]:
            cb(data)

    # ── PyTgCalls / VoIP Media ──────────────────────────────────────

    async def _init_pytgcalls(self):
        if not _HAS_PYTGCALLS or self._pytgcalls or not self.client or not self.is_connected:
            return
        self._pytgcalls = PyTgCalls(self.client)

        @self._pytgcalls.on_update()
        async def handle_update(client, update):
            if isinstance(update, ChatUpdate):
                if update.status & ChatUpdate.Status.INCOMING_CALL:
                    user_id = update.chat_id
                    self._current_call_chat_id = user_id
                    self._fire_call_event({
                        "user_id": user_id,
                        "type": "incoming",
                        "video": False,
                    })
                elif update.status & ChatUpdate.Status.DISCARDED_CALL:
                    user_id = self._current_call_chat_id
                    self.current_call = None
                    self._current_call_chat_id = None
                    self._fire_call_event({"type": "discarded", "user_id": user_id})

        await self._pytgcalls.start()
        # Monkey-patch _connect_call to set PLAYBACK stream before connect_p2p
        orig_connect = self._pytgcalls._connect_call
        svc = self

        async def patched_connect(chat_id, media_desc, config, payload):
            await orig_connect(chat_id, media_desc, config, payload)
            spk = svc._create_speaker_desc()
            if spk:
                try:
                    pb = ntgcalls.MediaDescription(
                        microphone=spk, speaker=None,
                        camera=None, screen=None,
                    )
                    await svc._pytgcalls._binding.set_stream_sources(
                        chat_id, ntgcalls.StreamMode.PLAYBACK, pb,
                    )
                except Exception:
                    pass

        self._pytgcalls._connect_call = patched_connect

    async def _stop_pytgcalls(self):
        if self._pytgcalls:
            try:
                if self._current_call_chat_id:
                    await self._pytgcalls.leave_call(self._current_call_chat_id)
            except Exception:
                pass
            self._pytgcalls = None
            self.current_call = None
            self._current_call_chat_id = None

    def _create_mic_desc(self):
        mics = MediaDevices.microphone_devices()
        mic = mics[0] if mics else None
        if mic:
            return ntgcalls.AudioDescription(
                ntgcalls.MediaSource.DEVICE,
                48000, 2,
                mic.metadata,
            )
        return None

    def _create_speaker_desc(self):
        speakers = MediaDevices.speaker_devices()
        sp = speakers[0] if speakers else None
        if sp:
            return ntgcalls.AudioDescription(
                ntgcalls.MediaSource.DEVICE,
                48000, 2,
                sp.metadata,
            )
        return None

    async def _create_media_stream(self, video: bool = False):
        mic_desc = self._create_mic_desc()
        camera_desc = None
        if video:
            cams = MediaDevices.camera_devices()
            if cams:
                cam = cams[0]
                camera_desc = ntgcalls.VideoDescription(
                    ntgcalls.MediaSource.DEVICE,
                    1280, 720, 30,
                    cam.metadata,
                )
        return ntgcalls.MediaDescription(
            microphone=mic_desc,
            speaker=None,
            camera=camera_desc,
            screen=None,
        )

    async def make_call(self, user_id: int, video: bool = False):
        if not self.client or not self.is_connected:
            return
        await self._init_pytgcalls()
        if not self._pytgcalls:
            return
        self._current_call_chat_id = user_id
        self._fire_call_event({
            "user_id": user_id,
            "type": "outgoing",
            "video": video,
        })
        try:
            media_desc = await self._create_media_stream(video)
            config = CallConfig(timeout=60)
            await self._pytgcalls._connect_call(
                user_id, media_desc, config, None,
            )
        except Exception as e:
            err_str = str(e)
            if "DH_G_A_HASH_INVALID" in err_str:
                logger.warning(f"Call DH key invalid, clearing cache: {e}")
                self._pytgcalls._p2p_configs.pop(user_id, None)
                try:
                    await self._pytgcalls._binding.stop(user_id)
                except Exception:
                    pass
            logger.error(f"Call failed: {e}")
            self._fire_call_event({"type": "discarded", "reason": str(e)})
            self._current_call_chat_id = None
            return
        self._fire_call_event({"type": "connected", "user_id": user_id})

    async def answer_call(self):
        if not self._pytgcalls or not self._current_call_chat_id:
            return
        chat_id = self._current_call_chat_id
        try:
            media_desc = await self._create_media_stream()
            config = CallConfig(timeout=60)
            await self._pytgcalls._connect_call(
                chat_id, media_desc, config, None,
            )
        except Exception as e:
            if "DH_G_A_HASH_INVALID" in str(e):
                logger.warning(f"Answer call DH key invalid, clearing cache: {e}")
                self._pytgcalls._p2p_configs.pop(chat_id, None)
                try:
                    await self._pytgcalls._binding.stop(chat_id)
                except Exception:
                    pass
            logger.error(f"Answer call failed: {e}")
            return
        self._fire_call_event({"type": "connected", "user_id": chat_id})

    async def reject_call(self):
        if not self._pytgcalls or not self._current_call_chat_id:
            return
        try:
            await self._pytgcalls.leave_call(self._current_call_chat_id)
        except Exception:
            await self._discard_call_legacy()
        user_id = self._current_call_chat_id
        self.current_call = None
        self._current_call_chat_id = None
        self._fire_call_event({"type": "discarded", "reason": "rejected", "user_id": user_id})

    async def end_call(self):
        if not self._pytgcalls or not self._current_call_chat_id:
            return
        try:
            await self._pytgcalls.leave_call(self._current_call_chat_id)
        except Exception:
            await self._discard_call_legacy()
        user_id = self._current_call_chat_id
        self.current_call = None
        self._current_call_chat_id = None
        self._fire_call_event({"type": "discarded", "reason": "ended", "user_id": user_id})

    async def _discard_call_legacy(self):
        if not self.client:
            return
        try:
            if self.current_call:
                await self.client(functions.phone.DiscardCallRequest(
                    call=InputPhoneCall(
                        id=self.current_call.id,
                        access_hash=self.current_call.access_hash,
                    ),
                ))
        except Exception:
            pass

    def on(self, event_type: str, callback: Callable):
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)

    async def send_message(self, chat_id: int, text: str):
        if self.client:
            await self.client.send_message(chat_id, text)

    async def send_file(self, chat_id: int, file_path: str):
        if self.client:
            await self.client.send_file(chat_id, file_path)

    async def get_contacts(self) -> List[dict]:
        if self.client:
            result = await self.client(functions.contacts.GetContactsRequest(hash=0))
            return [
                {
                    "id": c.id,
                    "first_name": c.first_name or "",
                    "last_name": c.last_name or "",
                    "phone": c.phone or "",
                    "username": c.username or "",
                }
                for c in result.users
            ]
        return []

    async def get_unread_count(self) -> int:
        if self.client:
            unread = 0
            async for dialog in self.client.iter_dialogs():
                if dialog.unread_count > 0:
                    unread += dialog.unread_count
            return unread
        return 0

    async def get_dialogs(self, limit: int = 50) -> List[dict]:
        if self.client:
            dialogs = []
            async for dialog in self.client.iter_dialogs(limit=limit):
                dialogs.append({
                    "id": dialog.id,
                    "name": dialog.name or "",
                    "unread_count": dialog.unread_count,
                    "is_read": dialog.unread_count == 0,
                    "last_message": dialog.message.text if dialog.message else "",
                    "is_pinned": dialog.pinned,
                })
            return dialogs
        return []

    async def get_user_dialogs(self, limit: int = 200) -> List[dict]:
        if not self.client:
            return []
        from telethon.tl.types import User as TLUser
        dialogs = []
        async for dialog in self.client.iter_dialogs(limit=limit):
            if not isinstance(dialog.entity, TLUser):
                continue
            if dialog.entity.bot:
                continue
            if dialog.id == 777000:
                continue
            dialogs.append({
                "id": dialog.id,
                "name": dialog.name or "",
                "unread_count": dialog.unread_count,
                "last_message": dialog.message.text if dialog.message else "",
                "is_pinned": dialog.pinned,
            })
        return dialogs

    async def mark_as_read(self, chat_id: int):
        if self.client:
            await self.client.send_read_acknowledge(chat_id)

    async def get_user_status(self, user_id: int) -> str:
        if self.client:
            try:
                user = await self.client.get_entity(user_id)
                status = user.status
                if isinstance(status, UserStatusOnline):
                    return "online"
                elif isinstance(status, UserStatusOffline):
                    was = status.was_online
                    now = datetime.now(timezone.utc)
                    diff = (now - was).total_seconds()
                    if diff < 60:
                        return "last seen just now"
                    elif diff < 3600:
                        return f"last seen {int(diff // 60)}m ago"
                    elif diff < 86400:
                        return f"last seen {int(diff // 3600)}h ago"
                    else:
                        return f"last seen {was.strftime('%b %d at %H:%M')}"
                elif isinstance(status, UserStatusRecently):
                    return "recently"
                elif isinstance(status, UserStatusLastWeek):
                    return "within_week"
                elif isinstance(status, UserStatusLastMonth):
                    return "within_month"
                return "unknown"
            except Exception:
                return "unknown"
        return "disconnected"

    async def _resolve_entity(self, chat_id):
        try:
            return await self.client.get_input_entity(chat_id)
        except (ValueError, TypeError):
            pass
        if isinstance(chat_id, int):
            s = str(chat_id)
            if len(s) > 9:
                try:
                    return await self.client.get_input_entity("+" + s)
                except (ValueError, TypeError):
                    pass
        return None

    async def get_messages(self, chat_id, limit: int = 50) -> List[dict]:
        if not self.client:
            return []
        messages = []
        try:
            entity = await self._resolve_entity(chat_id)
            if not entity:
                return [{"error": "Could not find this Telegram user. Have they messaged you yet?"}]
            async for msg in self.client.iter_messages(entity, limit=limit):
                sender = await msg.get_sender()
                media_info = self._extract_media_info(msg)
                if media_info:
                    asyncio.create_task(self._lazy_download_media(msg, media_info))

                entry = {
                    "id": msg.id,
                    "text": msg.text or "",
                    "date": msg.date.isoformat(),
                    "is_outgoing": msg.out,
                    "status": "read" if msg.out and getattr(msg, "read", False) else ("sent" if msg.out else None),
                    "sender_id": sender.id if sender else None,
                    "sender_name": getattr(sender, "first_name", "") or getattr(sender, "username", "") or "Unknown",
                    "media": media_info,
                }
                messages.append(entry)
        except Exception as e:
            messages.append({"error": str(e)})
        return messages
