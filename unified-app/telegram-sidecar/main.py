"""Line-delimited JSON bridge for one isolated Telegram account.

Raw Telegram identifiers exist only between this process and the Rust backend. The
backend applies the Supabase allowlist before anything is emitted to the webview.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError


def emit(event: str, data=None) -> None:
    sys.stdout.write(json.dumps({"event": event, "data": data or {}}, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def timestamp(value) -> int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    return int(datetime.now(timezone.utc).timestamp())


def media_type(message):
    if not message or not message.media:
        return None
    if getattr(message, "photo", None):
        return "image"
    document = getattr(message, "document", None)
    mime = getattr(document, "mime_type", "") or ""
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "document"


class TelegramBridge:
    def __init__(self, session_path: str):
        api_id = int(os.environ.get("TELEGRAM_API_ID", "0"))
        api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
        if not api_id or not api_hash:
            raise RuntimeError("Telegram API credentials are not configured")
        Path(session_path).parent.mkdir(parents=True, exist_ok=True)
        self.client = TelegramClient(session_path, api_id, api_hash)
        self.ready = False
        self.password_future = None

    async def start(self):
        await self.client.connect()
        self.client.add_event_handler(self.on_message, events.NewMessage)
        command_task = asyncio.create_task(self.command_loop())
        try:
            if not await self.client.is_user_authorized():
                await self.authorize_with_qr()
            self.ready = True
            emit("ready", {"name": "Telegram"})
            await command_task
        finally:
            command_task.cancel()
            await self.client.disconnect()

    async def authorize_with_qr(self):
        while not await self.client.is_user_authorized():
            qr = await self.client.qr_login()
            emit("qr", {"qrValue": qr.url})
            try:
                await qr.wait(timeout=55)
            except asyncio.TimeoutError:
                continue
            except SessionPasswordNeededError:
                loop = asyncio.get_running_loop()
                self.password_future = loop.create_future()
                emit("password-required", {})
                password = await self.password_future
                await self.client.sign_in(password=password)
                self.password_future = None

    async def command_loop(self):
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                return
            try:
                command = json.loads(line)
                await self.handle(command)
            except Exception:
                emit("error", {"message": "Telegram could not complete that action"})

    async def handle(self, command):
        action = command.get("action")
        request_id = command.get("requestId")
        data = command.get("data") or {}
        if action == "submitPassword":
            if self.password_future and not self.password_future.done():
                self.password_future.set_result(str(data.get("password", "")))
            return
        if action == "disconnect":
            return
        if not self.ready:
            emit("error", {"message": "Telegram is not connected", "requestId": request_id})
            return
        if action == "sendMessage":
            entity = await self.client.get_input_entity(int(data["chatId"]))
            message = await self.client.send_message(entity, str(data.get("message", "")))
            emit("message-sent", self.serialize(message, int(data["chatId"]), request_id))
        elif action == "sendFile":
            entity = await self.client.get_input_entity(int(data["chatId"]))
            message = await self.client.send_file(
                entity,
                str(data["filePath"]),
                caption=str(data.get("caption", "")),
            )
            emit("message-sent", self.serialize(message, int(data["chatId"]), request_id))
        elif action == "getMessages":
            chat_id = int(data["chatId"])
            entity = await self.client.get_input_entity(chat_id)
            messages = []
            async for message in self.client.iter_messages(entity, limit=50):
                messages.append(self.serialize(message, chat_id))
            emit("messages", list(reversed(messages)))
        elif action == "markRead":
            entity = await self.client.get_input_entity(int(data["chatId"]))
            await self.client.send_read_acknowledge(entity)

    async def on_message(self, event):
        if not self.ready or not event.is_private:
            return
        emit("new-message", self.serialize(event.message, int(event.chat_id)))

    @staticmethod
    def serialize(message, chat_id: int, request_id=None):
        result = {
            "id": str(message.id),
            "chatId": str(chat_id),
            "body": message.message or "",
            "timestamp": timestamp(message.date),
            "fromMe": bool(message.out),
            "hasMedia": bool(message.media),
            "mediaType": media_type(message),
        }
        if request_id:
            result["requestId"] = request_id
        return result


async def async_main():
    if len(sys.argv) != 2:
        raise RuntimeError("A Telegram session path is required")
    bridge = TelegramBridge(sys.argv[1])
    await bridge.start()


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass
    except Exception:
        emit("error", {"message": "Telegram runtime stopped unexpectedly"})
        raise
