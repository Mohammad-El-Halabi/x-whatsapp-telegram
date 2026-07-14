import customtkinter as ctk
from tkinter import messagebox, filedialog, Toplevel
from src.services.telegram_service import TelegramService
from src.services.supabase_service import SupabaseService
from src.models.schemas import StaffAssignment, User, ClientSecure
import threading
import asyncio
import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from typing import Optional
from datetime import datetime
import os
import json
import random
import subprocess
import platform
from pathlib import Path
from src.config.settings import AUTH_SESSION_FILE, SESSION_DIR, BASE_DIR
from src.services.sound_player import play_notification as _play_notification_sync, play_ringtone, stop_ringtone

def _play_notification_async():
    threading.Thread(target=_play_notification_sync, daemon=True).start()

# ── Taskbar badge support (Windows) ──────────────────────────────
_HAS_TASKBAR = False
_taskbar_list = None
_taskbar_window = None
try:
    import ctypes
    from ctypes import wintypes
    _HAS_TASKBAR = True
    _ole32 = ctypes.windll.ole32
    _ole32.CoInitialize(None)
    _CLSID_TaskbarList = ctypes.create_unicode_buffer("{56FDF344-FD6D-11d0-958A-006097C9A090}")
    _IID_ITaskbarList3 = ctypes.create_unicode_buffer("{EA1AFB91-9E28-4B86-90E4-9E9F8D5D7F2F}")
    class ITaskbarList3(ctypes.Structures):
        pass
    _taskbar_list = ctypes.POINTER(ITaskbarList3)()
    _CLSID = ctypes.create_unicode_buffer("{56FDF344-FD6D-11d0-958A-006097C9A090}")
    _IID = ctypes.create_unicode_buffer("{EA1AFB91-9E28-4B86-90E4-9E9F8D5D7F2F}")
    hr = _ole32.CoCreateInstance(
        ctypes.byref(ctypes.c_wchar_p(_CLSID.value)),
        None, 1,
        ctypes.byref(ctypes.c_wchar_p(_IID.value)),
        ctypes.byref(_taskbar_list)
    )
    if hr != 0:
        _taskbar_list = None
except Exception:
    _taskbar_list = None

_ICON_PATH = os.path.join(BASE_DIR, "icon.webp")
_ICO_PATH = os.path.join(BASE_DIR, "icon.ico")

def _ensure_icon():
    """Convert icon.webp to icon.ico if needed and return the ico path."""
    if os.path.exists(_ICO_PATH):
        return _ICO_PATH
    try:
        if os.path.exists(_ICON_PATH):
            img = Image.open(_ICON_PATH)
            img.save(_ICO_PATH, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
            return _ICO_PATH
    except Exception:
        pass
    return ""

def _set_taskbar_badge(count: int):
    """Set taskbar badge number on Windows via ITaskbarList3."""
    if not _taskbar_list or not _taskbar_window:
        return
    try:
        hwnd = ctypes.c_int(_taskbar_window.winfo_id())
        if count <= 0:
            _ole32.CoInitialize(None)
            _taskbar_list[0].SetOverlayIcon(hwnd, None, None)
        else:
            badge = _create_badge_icon(count)
            if badge:
                _taskbar_list[0].SetOverlayIcon(hwnd, badge, 0)
                ctypes.windll.user32.DestroyIcon(badge)
    except Exception:
        pass

def _create_badge_icon(count: int):
    """Create a small HICON with the count number drawn on it."""
    try:
        size = 24
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([0, 0, size - 1, size - 1], fill="#E53935")
        text = str(min(count, 99))
        try:
            font = ImageFont.truetype("segoeui.ttf", 11)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) // 2 - bbox[0]
        ty = (size - th) // 2 - bbox[1]
        draw.text((tx, ty), text, fill="white", font=font)
        from tkinter import _tkinter
        # Convert PIL image to HICON via pywin32 or direct bitmap
        # Use simple approach: save to temp .ico and load
        temp_ico = os.path.join(BASE_DIR, "session", f"_badge_{count}.ico")
        img.save(temp_ico, format="ICO", sizes=[(size, size)])
        hicon = ctypes.windll.user32.LoadImageW(
            0, temp_ico, 1, size, size, 0x00000010
        )
        return hicon
    except Exception:
        return None

import customtkinter.windows.widgets.core_rendering.draw_engine as _draw_engine
_orig_draw = _draw_engine.DrawEngine._DrawEngine__draw_rounded_rect_with_border_font_shapes
def _safe_draw(self, width, height, corner_radius, border_width, inner_corner_radius, *args):
    try:
        return _orig_draw(self, width, height, corner_radius, border_width, inner_corner_radius, *args)
    except Exception:
        pass
_draw_engine.DrawEngine._DrawEngine__draw_rounded_rect_with_border_font_shapes = _safe_draw

# ── Telegram Light Palette (v5.0 accurate colors) ────────────────
PRIMARY_BLUE    = "#3390EC"
ACCENT_BLUE     = "#3A9BEF"
STATUS_BLUE     = "#5EB8F2"
OUTGOING_BG     = "#EFFDDE"
OUTGOING_BG2    = "#E5F9C8"
INCOMING_BG     = "#FFFFFF"
SIDEBAR_BG      = "#FFFFFF"
HEADER_BG       = "#FFFFFF"
SEARCH_BG       = "#F0F0F0"
WALLPAPER_BG    = "#E6EBE0"
TEXT_PRIMARY    = "#000000"
TEXT_SECONDARY  = "#8D8D8D"
TEXT_MUTED      = "#ADADAD"
CHECK_READ      = "#5BC44E"
CHECK_SENT      = "#8D8D8D"
DIVIDER         = "#E7E7E7"
HOVER_ROW       = "#F4F4F4"
SELECTED_ROW    = "#3390EC"
DANGER          = "#E53935"
GREEN           = "#4ACB60"
WARNING         = "#F39C11"
INPUT_BORDER    = "#DBDBDB"
BUBBLE_SHADOW   = "#C8C8C8"
REPLY_ACCENT    = "#3390EC"
AVATAR_BG       = "#3390EC"
SIDEBAR_WIDTH   = 285
HEADER_HEIGHT   = 54
BUBBLE_RADIUS   = 7
INPUT_HEIGHT    = 54
FONT_FAMILY     = "Segoe UI"
FONT_SIZE_NAME  = 14
FONT_SIZE_MSG   = 13
FONT_SIZE_TIME  = 10
FONT_SIZE_PREVIEW = 12
FONT_SIZE_SEARCH = 13
AVATAR_SIZE     = 46
AVATAR_FONT_SIZE = 18

# ── Generate wallpaper pattern ──────────────────────────────────
def _create_wallpaper(width, height):
    img = Image.new("RGB", (width, height), (232, 240, 228))
    draw = ImageDraw.Draw(img)
    rng = random.Random(42)
    for _ in range(60):
        cx = rng.randint(0, width)
        cy = rng.randint(0, height)
        r = rng.randint(20, 60)
        shade = rng.randint(210, 245)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(shade, min(255, shade+10), shade-5), outline=None)
    for _ in range(30):
        cx = rng.randint(0, width)
        cy = rng.randint(0, height)
        r = rng.randint(4, 12)
        shade = rng.randint(200, 240)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(255, 255, 255), outline=None)
    for _ in range(80):
        sx = rng.randint(0, width)
        sy = rng.randint(0, height)
        sw = rng.randint(3, 8)
        sh = rng.randint(30, 70)
        shade = rng.randint(180, 210)
        draw.ellipse([sx-sw//2, sy, sx+sw//2, sy+sh], fill=(shade-30, shade, shade-40), outline=None)
    img = img.filter(ImageFilter.GaussianBlur(radius=18))
    return img


class TelegramApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Telegram Staff")
        self.geometry("1100x720")
        self.minsize(800, 500)
        self.configure(fg_color=SIDEBAR_BG)

        self.supabase = SupabaseService()
        self.workers: dict[str, "TelegramWorker"] = {}
        self.current_user = None

        self.selected_chat_id: Optional[int] = None
        self.selected_chat_name = ""
        self.chat_map: dict[int, dict] = {}
        self.messages_cache: dict[int, list] = {}
        self.assigned_clients: list[ClientSecure] = []
        self.telegram_dialogs: list[dict] = []
        self.current_worker: Optional["TelegramWorker"] = None

        self._ctkimgs: list = []
        self._after_ids: set = set()
        self._wallpaper_img = None
        self._wallpaper_ctk = None
        self._wallpaper_last_w = 0
        self._wallpaper_last_h = 0
        self._lock = threading.RLock()
        self._voice_recording = False
        self._voice_thread = None
        self._voice_data = []
        self._voice_stream = None
        self._total_unread = 0
        self._msg_queue = []
        self._msg_queue_timer = None
        self._setup_ui()
        self._set_window_icon()
        self.after(100, self._try_restore_session)
        self.protocol("WM_DELETE_WINDOW", self._cleanup)

    def _safe_after(self, ms, func, *args):
        wrapper = [None]
        def _callback():
            self._after_ids.discard(wrapper[0])
            if not self.winfo_exists():
                return
            try:
                func(*args)
            except Exception:
                pass
        wrapper[0] = self.after(ms, _callback)
        self._after_ids.add(wrapper[0])
        return wrapper[0]

    def _cancel_pending(self):
        for aid in list(self._after_ids):
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        self._msg_queue.clear()
        if self._msg_queue_timer:
            try:
                self.after_cancel(self._msg_queue_timer)
            except Exception:
                pass
            self._msg_queue_timer = None

    def _cleanup(self):
        self._cancel_pending()
        self._clean_media_cache()
        try:
            self._stop_voice_recording()
        except Exception:
            pass
        stop_ringtone()
        for gw, worker in list(self.workers.items()):
            try:
                worker.disconnect()
            except Exception:
                pass
        self.workers.clear()
        try:
            self.destroy()
        except Exception:
            pass

    def _clean_media_cache(self):
        self._ctkimgs.clear()
        self._wallpaper_img = None
        self._wallpaper_ctk = None
        try:
            for f in Path(BASE_DIR / "session").glob("_badge_*.ico"):
                f.unlink(missing_ok=True)
        except Exception:
            pass

    def _setup_ui(self):
        self._setup_login()
        self._setup_main()
        self._session_restored = False

    def _try_restore_session(self):
        try:
            if AUTH_SESSION_FILE.exists():
                data = json.loads(AUTH_SESSION_FILE.read_text())
                access_token = data.get("access_token")
                refresh_token = data.get("refresh_token")
                if access_token:
                    self.supabase.client.auth.set_session(access_token, refresh_token)
                    au = self.supabase.get_current_user()
                    if au and au.user:
                        user = self.supabase.get_user_by_id(au.user.id)
                        if user:
                            self._session_restored = True
                            self.current_user = user
                            self.login_frame.pack_forget()
                            self.main_frame.pack(fill="both", expand=True)
                            self._load_assignments()
                            return
        except Exception:
            pass
        # Session invalid or missing — show login
        self.login_frame.pack(fill="both", expand=True)

    def _setup_login(self):
        self.login_frame = ctk.CTkFrame(self, fg_color=SEARCH_BG)

        card = ctk.CTkFrame(self.login_frame, fg_color=SIDEBAR_BG, corner_radius=16, width=420, height=500,
                            border_width=1, border_color=INPUT_BORDER)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="\U0001f916", font=(FONT_FAMILY, 48)).pack(pady=(40, 0))
        ctk.CTkLabel(card, text="Telegram Staff", font=(FONT_FAMILY, 22, "bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(8, 25))

        for label, attr, ph, show in [
            ("Email", "email", "staff@example.com", None),
            ("Password", "password", "Password", "\u2022"),
        ]:
            ctk.CTkLabel(card, text=label, font=(FONT_FAMILY, 12), text_color=TEXT_SECONDARY,
                         anchor="w").pack(fill="x", padx=40, pady=(6, 2))
            e = ctk.CTkEntry(card, placeholder_text=ph, show=show, width=340, height=42,
                              fg_color=SEARCH_BG, border_width=1, border_color=INPUT_BORDER,
                              corner_radius=8, text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED)
            e.pack(padx=40, pady=(0, 4))
            setattr(self, f"{attr}_entry", e)

        self.login_btn = ctk.CTkButton(card, text="Sign In", command=self._handle_login,
                                        width=340, height=44, fg_color=PRIMARY_BLUE,
                                        hover_color=ACCENT_BLUE, corner_radius=8,
                                        font=(FONT_FAMILY, 14, "bold"))
        self.login_btn.pack(padx=40, pady=(18, 6))
        self.login_status = ctk.CTkLabel(card, text="", font=(FONT_FAMILY, 11), text_color=DANGER)
        self.login_status.pack(padx=40, pady=(0, 10))

    def _setup_main(self):
        self.main_frame = ctk.CTkFrame(self, fg_color=SIDEBAR_BG)

        # ── Left sidebar ────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self.main_frame, fg_color=SIDEBAR_BG, width=SIDEBAR_WIDTH, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Sidebar header — hamburger, title, status
        sh = ctk.CTkFrame(self.sidebar, fg_color=HEADER_BG, height=HEADER_HEIGHT, corner_radius=0)
        sh.pack(fill="x")
        sh.pack_propagate(False)
        h_inner = ctk.CTkFrame(sh, fg_color="transparent")
        h_inner.pack(fill="both", padx=12, pady=8)

        ctk.CTkLabel(h_inner, text="\u2261", font=(FONT_FAMILY, 22), text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(h_inner, text="Telegram Staff", font=(FONT_FAMILY, 15, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left", padx=(10, 0))

        self.status_dot = ctk.CTkLabel(h_inner, text="\u25cf", text_color=TEXT_MUTED,
                                        font=(FONT_FAMILY, 14))
        self.status_dot.pack(side="right", padx=(0, 2))

        # Search bar
        search_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        search_frame.pack(fill="x", padx=8, pady=(5, 7))
        search_bg = ctk.CTkFrame(search_frame, fg_color=SEARCH_BG, corner_radius=8, height=36)
        search_bg.pack(fill="x")
        search_bg.pack_propagate(False)
        search_inner = ctk.CTkFrame(search_bg, fg_color="transparent")
        search_inner.pack(fill="both", padx=8, pady=2)
        ctk.CTkLabel(search_inner, text="\U0001f50d", font=(FONT_FAMILY, 13),
                     text_color=TEXT_MUTED).pack(side="left", padx=(0, 4))
        self.search_entry = ctk.CTkEntry(search_inner, placeholder_text="Search", height=28,
                                          fg_color="transparent", border_width=0, corner_radius=0,
                                          text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED,
                                          font=(FONT_FAMILY, FONT_SIZE_SEARCH))
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_chats())

        # Chat list
        self.chat_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", corner_radius=0)
        self.chat_list.pack(fill="both", expand=True, padx=0, pady=0)

        # Sidebar bottom: connect button (only shown when not connected)
        self.sidebar_bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_bottom.pack(fill="x", padx=8, pady=(2, 8))
        self.connect_btn = ctk.CTkButton(self.sidebar_bottom, text="Connect to Telegram",
                                          command=self._connect_account,
                                          fg_color=PRIMARY_BLUE, hover_color=ACCENT_BLUE, corner_radius=8,
                                          height=34, font=(FONT_FAMILY, 13, "bold"))
        self.connect_btn.pack(fill="x")

        # ── Right main area ─────────────────────────────────────────
        self.main_area = ctk.CTkFrame(self.main_frame, fg_color=WALLPAPER_BG)
        self.main_area.pack(side="right", fill="both", expand=True)
        self._show_welcome()

    def _set_window_icon(self):
        ico = _ensure_icon()
        if ico:
            try:
                self.iconbitmap(ico)
            except Exception:
                pass
        global _taskbar_window
        _taskbar_window = self

    def _update_badge(self):
        total = 0
        with self._lock:
            for cid, info in self.chat_map.items():
                if cid != self.selected_chat_id:
                    total += info.get("unread_count", 0)
            self._total_unread = total
        if total > 0:
            self.title(f"Telegram Staff ({total})")
        else:
            self.title("Telegram Staff")
        _set_taskbar_badge(total)
        self._safe_after(5000, self._update_badge)

    def _show_welcome(self):
        self._cancel_pending()
        for w in self.main_area.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        f = ctk.CTkFrame(self.main_area, fg_color="transparent")
        f.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(f, text="\U0001f916", font=(FONT_FAMILY, 64)).pack()
        ctk.CTkLabel(f, text="Select a staff member to start messaging",
                     font=(FONT_FAMILY, 15), text_color=TEXT_SECONDARY).pack(pady=(8, 0))

    # ── Loading / Empty State Helpers ──────────────────────────────

    def _show_loading_sidebar(self):
        """Show loading indicator in the chat list area."""
        try:
            self._hide_loading_sidebar()
            f = ctk.CTkFrame(self.chat_list, fg_color="transparent", height=60)
            f.pack(fill="x", pady=20)
            prog = ctk.CTkProgressBar(f, width=200, height=4, corner_radius=2,
                                       fg_color=DIVIDER, progress_color=PRIMARY_BLUE)
            prog.pack(pady=(0, 6))
            prog.start()
            ctk.CTkLabel(f, text="Loading\u2026", font=(FONT_FAMILY, 12),
                         text_color=TEXT_MUTED).pack()
            self._sidebar_loading_ref = (f, prog)
        except Exception:
            pass

    def _hide_loading_sidebar(self):
        try:
            ref = getattr(self, '_sidebar_loading_ref', None)
            if ref:
                f, prog = ref
                try:
                    prog.stop()
                except Exception:
                    pass
                try:
                    f.destroy()
                except Exception:
                    pass
                self._sidebar_loading_ref = None
        except Exception:
            pass

    def _show_loading_messages(self):
        """Show loading indicator in the messages area."""
        try:
            self._hide_loading_messages()
            f = ctk.CTkFrame(self._msg_inner if hasattr(self, '_msg_inner') and self._msg_inner.winfo_exists() else self.main_area,
                             fg_color="transparent")
            f.place(relx=0.5, rely=0.35, anchor="center")
            prog = ctk.CTkProgressBar(f, width=200, height=4, corner_radius=2,
                                       fg_color=DIVIDER, progress_color=PRIMARY_BLUE)
            prog.pack(pady=(0, 8))
            prog.start()
            ctk.CTkLabel(f, text="Loading messages\u2026", font=(FONT_FAMILY, 13),
                         text_color=TEXT_MUTED).pack()
            self._msg_loading_ref = (f, prog)
        except Exception:
            pass

    def _hide_loading_messages(self):
        try:
            ref = getattr(self, '_msg_loading_ref', None)
            if ref:
                f, prog = ref
                try:
                    prog.stop()
                except Exception:
                    pass
                try:
                    f.destroy()
                except Exception:
                    pass
                self._msg_loading_ref = None
        except Exception:
            pass

    def _show_empty_chat(self, text="No conversations yet"):
        """Show empty state placeholder in the chat list area."""
        try:
            for w in self.chat_list.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
            f = ctk.CTkFrame(self.chat_list, fg_color="transparent")
            f.pack(fill="both", expand=True, pady=40)
            ctk.CTkLabel(f, text="\U0001f4ad", font=(FONT_FAMILY, 36),
                         text_color=TEXT_MUTED).pack(pady=(20, 6))
            ctk.CTkLabel(f, text=text, font=(FONT_FAMILY, 13),
                         text_color=TEXT_MUTED).pack()
        except Exception:
            pass

    def _show_empty_messages(self):
        """Show empty state in the messages area when no messages exist."""
        try:
            if not hasattr(self, '_msg_inner') or not self._msg_inner.winfo_exists():
                return
            for w in self._msg_inner.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
            f = ctk.CTkFrame(self._msg_inner, fg_color="transparent")
            f.place(relx=0.5, rely=0.4, anchor="center")
            ctk.CTkLabel(f, text="\U0001f4ac", font=(FONT_FAMILY, 36),
                         text_color=TEXT_MUTED).pack(pady=(0, 6))
            ctk.CTkLabel(f, text="No messages yet",
                         font=(FONT_FAMILY, 13), text_color=TEXT_MUTED).pack()
            ctk.CTkLabel(f, text="Send a message to start the conversation",
                         font=(FONT_FAMILY, 11), text_color=TEXT_MUTED).pack(pady=(2, 0))
        except Exception:
            pass

    def _show_progress_overlay(self, text="Sending\u2026"):
        """Show a progress overlay in the main area for long operations."""
        try:
            self._hide_progress_overlay()
            f = ctk.CTkFrame(self.main_area, fg_color=SIDEBAR_BG, corner_radius=12,
                             border_width=1, border_color=INPUT_BORDER)
            f.place(relx=0.5, rely=0.5, anchor="center", width=260, height=90)
            prog = ctk.CTkProgressBar(f, width=200, height=6, corner_radius=3,
                                       fg_color=DIVIDER, progress_color=PRIMARY_BLUE)
            prog.place(relx=0.5, rely=0.3, anchor="center")
            prog.start()
            ctk.CTkLabel(f, text=text, font=(FONT_FAMILY, 13),
                         text_color=TEXT_SECONDARY).place(relx=0.5, rely=0.65, anchor="center")
            self._progress_overlay = (f, prog)
        except Exception:
            pass

    def _hide_progress_overlay(self):
        try:
            ref = getattr(self, '_progress_overlay', None)
            if ref:
                f, prog = ref
                try:
                    prog.stop()
                except Exception:
                    pass
                try:
                    f.destroy()
                except Exception:
                    pass
                self._progress_overlay = None
        except Exception:
            pass

    # ── CHAT VIEW ───────────────────────────────────────────────────

    def _build_chat_view(self):
        self._cancel_pending()
        try:
            self.update_idletasks()
        except Exception:
            pass
        for w in self.main_area.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        self._ensure_wallpaper()

        wallpaper_container = ctk.CTkFrame(self.main_area, fg_color=WALLPAPER_BG, corner_radius=0)

        if self._wallpaper_ctk:
            wall_lbl = ctk.CTkLabel(wallpaper_container, image=self._wallpaper_ctk, text="",
                                     fg_color=WALLPAPER_BG)
            wall_lbl.place(relx=0.5, rely=0.5, anchor="center")
            wall_lbl.lower()

        wallpaper_container.pack(fill="both", expand=True)

        # ── Connection warning banner ────────────────────────────────
        if not self.current_worker or not self.current_worker.service.is_connected:
            warn_frame = ctk.CTkFrame(wallpaper_container, fg_color=WARNING, height=32, corner_radius=0)
            warn_frame.pack(fill="x")
            warn_frame.pack_propagate(False)
            ctk.CTkLabel(warn_frame, text="\u26a0  Not connected to Telegram  \u26a0",
                         font=(FONT_FAMILY, 11, "bold"), text_color=SIDEBAR_BG).pack(expand=True)

        # ── Chat Header (Telegram-style) ─────────────────────────────
        self.chat_header = ctk.CTkFrame(wallpaper_container, fg_color=HEADER_BG, height=HEADER_HEIGHT, corner_radius=0)
        self.chat_header.pack(fill="x")
        self.chat_header.pack_propagate(False)

        # Header bottom border
        header_line = ctk.CTkFrame(self.chat_header, fg_color=DIVIDER, height=1)
        header_line.pack(fill="x", side="bottom")

        h = ctk.CTkFrame(self.chat_header, fg_color="transparent")
        h.pack(fill="both", padx=10, pady=5)

        initial = self.selected_chat_name[0].upper() if self.selected_chat_name else "?"
        self.chat_avatar = ctk.CTkLabel(h, text=initial, font=(FONT_FAMILY, AVATAR_FONT_SIZE, "bold"),
                                         text_color=SIDEBAR_BG, width=40, height=40,
                                         fg_color=AVATAR_BG, corner_radius=20)
        self.chat_avatar.pack(side="left")

        info = ctk.CTkFrame(h, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.chat_title = ctk.CTkLabel(info, text="", font=(FONT_FAMILY, FONT_SIZE_NAME, "bold"),
                                        text_color=TEXT_PRIMARY, anchor="w")
        self.chat_title.pack(fill="x")
        self.chat_status_lbl = ctk.CTkLabel(info, text="", font=(FONT_FAMILY, 12),
                                             text_color=TEXT_SECONDARY, anchor="w")
        self.chat_status_lbl.pack(fill="x")

        btn_frame = ctk.CTkFrame(h, fg_color="transparent")
        btn_frame.pack(side="right")

        call_btn = ctk.CTkButton(btn_frame, text="\U0001f4de", width=36, height=36, corner_radius=18,
                                  fg_color="transparent", hover_color=HOVER_ROW,
                                  text_color=TEXT_SECONDARY, font=(FONT_FAMILY, 18),
                                  command=lambda: self._make_call(video=False))
        call_btn.pack(side="left", padx=2)

        # ── Messages area ────────────────────────────────────────────
        self.msg_container = ctk.CTkScrollableFrame(wallpaper_container, fg_color="transparent", corner_radius=0)
        self.msg_container.pack(fill="both", expand=True, padx=0, pady=0)

        self._msg_inner = ctk.CTkFrame(self.msg_container, fg_color="transparent")
        self._msg_inner.pack(fill="both", expand=True, padx=36, pady=6)

        # Scroll-to-bottom button (shown when scrolled up)
        self._scroll_down_btn = ctk.CTkButton(wallpaper_container, text="\u25bc", width=40, height=40,
                                                corner_radius=20, fg_color=PRIMARY_BLUE,
                                                hover_color=ACCENT_BLUE, text_color=SIDEBAR_BG,
                                                font=(FONT_FAMILY, 16),
                                                command=self._scroll_bottom)
        self._scroll_down_btn.place(relx=1.0, rely=1.0, anchor="se", x=-16, y=-60)
        self._scroll_down_btn.lower()
        self._scroll_down_btn.bind("<Button-1>", lambda e: self._scroll_bottom())

        def _on_scroll(event):
            try:
                canvas = self.msg_container._parent_canvas
                top = canvas.yview()[0]
                if top < 0.85:
                    self._scroll_down_btn.lift()
                    self._scroll_down_btn.configure(fg_color=PRIMARY_BLUE)
                else:
                    self._scroll_down_btn.lower()
            except Exception:
                pass
        try:
            self.msg_container._parent_canvas.bind("<Configure>", _on_scroll, add="+")
        except Exception:
            pass

        # ── Bottom input bar (Telegram-style) ────────────────────────
        self.input_bar = ctk.CTkFrame(wallpaper_container, fg_color=HEADER_BG, height=INPUT_HEIGHT, corner_radius=0)
        self.input_bar.pack(fill="x")
        self.input_bar.pack_propagate(False)

        # Top border for input bar
        top_line = ctk.CTkFrame(self.input_bar, fg_color=DIVIDER, height=1)
        top_line.pack(fill="x")

        ib = ctk.CTkFrame(self.input_bar, fg_color="transparent")
        ib.pack(fill="both", padx=8, pady=6)

        is_connected = self.current_worker and self.current_worker.service.is_connected
        input_disabled = not is_connected

        self.attach_btn = ctk.CTkButton(ib, text="\U0001f4ce", width=38, height=38,
                                         fg_color="transparent", hover_color=HOVER_ROW,
                                         text_color=TEXT_MUTED if input_disabled else TEXT_SECONDARY,
                                         corner_radius=19, state="disabled" if input_disabled else "normal",
                                         font=(FONT_FAMILY, 18),
                                         command=self._send_file_dialog)
        self.attach_btn.pack(side="left", padx=(0, 4))

        msg_frame = ctk.CTkFrame(ib, fg_color=SEARCH_BG, corner_radius=10, height=38)
        msg_frame.pack(side="left", fill="x", expand=True, padx=(0, 4))
        msg_frame.pack_propagate(False)

        self.message_entry = ctk.CTkEntry(msg_frame, placeholder_text="Message" if is_connected else "Connect to send messages",
                                           height=34, state="normal" if is_connected else "disabled",
                                           fg_color="transparent", border_width=0, corner_radius=0,
                                           font=(FONT_FAMILY, FONT_SIZE_MSG), text_color=TEXT_PRIMARY,
                                           placeholder_text_color=TEXT_MUTED)
        self.message_entry.pack(fill="x", padx=10, pady=2)
        self.message_entry.bind("<Return>", lambda e: self._send_message())
        self.message_entry.bind("<Button-1>", lambda e: self.message_entry.focus_set())

        self.emoji_btn = ctk.CTkButton(ib, text="\U0001f600", width=38, height=38,
                                        fg_color="transparent", hover_color=HOVER_ROW,
                                        text_color=TEXT_MUTED if input_disabled else TEXT_SECONDARY,
                                        corner_radius=19, state="disabled" if input_disabled else "normal",
                                        font=(FONT_FAMILY, 18),
                                        command=self._toggle_emoji_picker)
        self.emoji_btn.pack(side="left", padx=(0, 2))

        self.mic_btn = ctk.CTkButton(ib, text="\U0001f3a4", width=38, height=38,
                                      fg_color="transparent", hover_color=HOVER_ROW,
                                      text_color=TEXT_MUTED if input_disabled else TEXT_SECONDARY,
                                      corner_radius=19, state="disabled" if input_disabled else "normal",
                                      font=(FONT_FAMILY, 18),
                                      command=self._toggle_voice_recording)
        self.mic_btn.pack(side="left", padx=(0, 2))

        self.send_btn = ctk.CTkButton(ib, text="\U00002795", width=38, height=38,
                                       fg_color=TEXT_MUTED if input_disabled else PRIMARY_BLUE,
                                       hover_color=ACCENT_BLUE, state="disabled" if input_disabled else "normal",
                                       text_color=SIDEBAR_BG, corner_radius=19,
                                       font=(FONT_FAMILY, 18),
                                       command=self._send_message)
        self.send_btn.pack(side="left")

    def _ensure_wallpaper(self):
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            if w < 100 or h < 100:
                w, h = 800, 600
            if self._wallpaper_img is None or \
               abs(self._wallpaper_last_w - w) > 50 or abs(self._wallpaper_last_h - h) > 50:
                self._wallpaper_last_w = w
                self._wallpaper_last_h = h
                img = _create_wallpaper(w, h)
                self._wallpaper_img = img
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
                self._wallpaper_ctk = ctk_img
        except Exception:
            pass

    # ── CHAT LIST ──────────────────────────────────────────────────

    def _build_chat_items(self):
        """Build sorted list of (chat_id, name, unread, last_message, client) from current data."""
        client_map: dict[int, ClientSecure] = {}
        for c in self.assigned_clients:
            pid = c.platform_identifiers or {}
            tg_id_str = pid.get("telegram", "")
            if not tg_id_str:
                continue
            try:
                cid = int(tg_id_str)
                client_map[cid] = c
            except (ValueError, TypeError):
                pass

        dialogs = self.telegram_dialogs

        if dialogs:
            items = []
            for d in dialogs:
                did = d["id"]
                dname = d["name"]
                unread = d.get("unread_count", 0)
                last_msg = d.get("last_message", "")
                last_ts = d.get("last_timestamp", 0.0)
                client = client_map.get(did)
                name = client.masked_identity or dname if client else dname
                items.append((did, name, unread, last_msg, last_ts, client))
            items.sort(key=lambda x: x[4], reverse=True)
        else:
            items = []
            for c in self.assigned_clients:
                pid = c.platform_identifiers or {}
                tg_id_str = pid.get("telegram", "")
                if not tg_id_str:
                    continue
                try:
                    cid = int(tg_id_str)
                except (ValueError, TypeError):
                    continue
                name = c.masked_identity or f"Client {tg_id_str}"
                items.append((cid, name, 0, "", 0.0, c))
        return items

    def _display_client_list(self):
        self._hide_loading_sidebar()
        if hasattr(self, '_display_throttle') and self._display_throttle:
            return
        self._display_throttle = True
        self._safe_after(200, lambda: setattr(self, '_display_throttle', False))
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            for w in self.chat_list.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        self._chat_rows = {}

        with self._lock:
            self.chat_map.clear()
            items = self._build_chat_items()

            if not items:
                self._show_empty_chat("No conversations yet")
                return

            for cid, name, unread, last_msg, last_ts, client in items:
                try:
                    self.chat_map[cid] = {"name": name, "unread_count": unread,
                                          "last_message": last_msg, "last_timestamp": last_ts,
                                          "client": client}
                except Exception:
                    pass

                row, refs = self._build_chat_row(cid, name, unread, last_msg, client)
                self._chat_rows[cid] = refs

        self._filter_chats()

    def _build_chat_row(self, cid, name, unread, last_msg, client):
        row = ctk.CTkFrame(self.chat_list, fg_color="transparent", height=68, corner_radius=0)
        row.pack(fill="x")
        row.pack_propagate(False)

        is_sel = cid == self.selected_chat_id
        if is_sel:
            row.configure(fg_color=PRIMARY_BLUE)

        initial = name[0].upper() if name and name[0].strip() else "?"
        avatar_color = AVATAR_BG if not is_sel else SIDEBAR_BG
        avatar_text_color = SIDEBAR_BG if not is_sel else PRIMARY_BLUE
        avatar = ctk.CTkLabel(row, text=initial, font=(FONT_FAMILY, AVATAR_FONT_SIZE, "bold"),
                               text_color=avatar_text_color, width=AVATAR_SIZE, height=AVATAR_SIZE,
                               fg_color=avatar_color, corner_radius=AVATAR_SIZE // 2)
        avatar.pack(side="left", padx=(12, 8), pady=10)

        info_f = ctk.CTkFrame(row, fg_color="transparent")
        info_f.pack(side="left", fill="both", expand=True, pady=10)

        top = ctk.CTkFrame(info_f, fg_color="transparent")
        top.pack(fill="x")
        name_color = SIDEBAR_BG if is_sel else TEXT_PRIMARY
        name_lbl = ctk.CTkLabel(top, text=name, font=(FONT_FAMILY, FONT_SIZE_NAME, "bold"),
                                 text_color=name_color, anchor="w")
        name_lbl.pack(side="left")

        ts_color = SIDEBAR_BG if is_sel else TEXT_MUTED
        ts_lbl = ctk.CTkLabel(top, text="", font=(FONT_FAMILY, FONT_SIZE_TIME),
                              text_color=ts_color, anchor="e")
        ts_lbl.pack(side="right")

        bottom = ctk.CTkFrame(info_f, fg_color="transparent")
        bottom.pack(fill="x", pady=(1, 0))

        preview_color = SIDEBAR_BG if is_sel else TEXT_SECONDARY
        preview_text = (last_msg[:65] + "\u2026") if last_msg and len(last_msg) > 65 else (last_msg or "")
        preview = ctk.CTkLabel(bottom, text=preview_text, font=(FONT_FAMILY, FONT_SIZE_PREVIEW),
                                text_color=preview_color, anchor="w")
        preview.pack(side="left", fill="x", expand=True)

        right_grp = ctk.CTkFrame(bottom, fg_color="transparent")
        right_grp.pack(side="right", padx=(4, 8))

        badge = ctk.CTkLabel(right_grp, text="", font=(FONT_FAMILY, FONT_SIZE_TIME, "bold"),
                              fg_color="transparent", corner_radius=9, width=18, height=18)
        badge.pack(side="right")

        sep = ctk.CTkFrame(self.chat_list, fg_color=DIVIDER, height=1)
        sep.pack(fill="x", padx=(72, 0))

        # Hover effect
        def _on_enter(e, r=row):
            if r.cget("fg_color") != PRIMARY_BLUE:
                r.configure(fg_color=HOVER_ROW)
        def _on_leave(e, r=row):
            if r.cget("fg_color") != PRIMARY_BLUE:
                r.configure(fg_color="transparent")

        row.bind("<Button-1>", lambda e, cid=cid: self._select_chat(cid))
        row.bind("<Enter>", _on_enter)
        row.bind("<Leave>", _on_leave)
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, cid=cid: self._select_chat(cid))

        refs = {
            "frame": row, "sep": sep, "preview": preview, "badge": badge,
            "ts_lbl": ts_lbl, "name_lbl": name_lbl, "avatar": avatar,
            "info_f": info_f, "top": top, "bottom": bottom, "right_grp": right_grp,
        }
        return row, refs

    def _update_chat_row(self, cid, name, unread, last_msg, last_ts, client):
        rows = getattr(self, '_chat_rows', None)
        if rows is None:
            return False
        refs = rows.get(cid)
        if not refs:
            return False
        with self._lock:
            self.chat_map[cid] = {"name": name, "unread_count": unread,
                                  "last_message": last_msg, "last_timestamp": last_ts,
                                  "client": client}
        try:
            is_sel = cid == self.selected_chat_id
            preview_text = (last_msg[:65] + "\u2026") if last_msg and len(last_msg) > 65 else (last_msg or "")
            refs["preview"].configure(text=preview_text)
            if unread > 0 and not is_sel:
                refs["badge"].configure(text=str(unread), fg_color=PRIMARY_BLUE, text_color=SIDEBAR_BG)
            else:
                refs["badge"].configure(text="", fg_color="transparent")
            self._update_row_colors(cid, refs, is_sel)
            if last_ts:
                try:
                    dt = datetime.fromtimestamp(last_ts)

                    now = datetime.now()
                    if dt.date() == now.date():
                        ts = dt.strftime("%I:%M %p").lstrip("0").lower()
                    else:
                        ts = dt.strftime("%b %d").lower()
                except Exception:
                    ts = ""
                refs["ts_lbl"].configure(text=ts)
            return True
        except Exception:
            return False

    def _update_row_colors(self, cid, refs, is_sel):
        try:
            bg = PRIMARY_BLUE if is_sel else "transparent"
            refs["frame"].configure(fg_color=bg)
            ncol = SIDEBAR_BG if is_sel else TEXT_PRIMARY
            refs["name_lbl"].configure(text_color=ncol)
            pcol = SIDEBAR_BG if is_sel else TEXT_SECONDARY
            refs["preview"].configure(text_color=pcol)
            tcol = SIDEBAR_BG if is_sel else TEXT_MUTED
            refs["ts_lbl"].configure(text_color=tcol)
            ac = AVATAR_BG if not is_sel else SIDEBAR_BG
            atc = SIDEBAR_BG if not is_sel else PRIMARY_BLUE
            refs["avatar"].configure(fg_color=ac, text_color=atc)
            # Update hover bindings
            def _on_enter(e, r=refs["frame"]):
                if r.cget("fg_color") != PRIMARY_BLUE:
                    r.configure(fg_color=HOVER_ROW)
            def _on_leave(e, r=refs["frame"]):
                if r.cget("fg_color") != PRIMARY_BLUE:
                    r.configure(fg_color="transparent")
            refs["frame"].bind("<Enter>", _on_enter)
            refs["frame"].bind("<Leave>", _on_leave)
        except Exception:
            pass

    def _filter_chats(self):
        q = self.search_entry.get().strip().lower()
        for w in self.chat_list.winfo_children():
            if isinstance(w, ctk.CTkFrame) and w.winfo_children():
                try:
                    info_f = w.winfo_children()[1]
                    name_label = info_f.winfo_children()[0].winfo_children()[0]
                    name = name_label.cget("text").lower()
                    w.pack() if q in name else w.pack_forget()
                except Exception:
                    w.pack()
            elif not q:
                w.pack()

    def _focus_search(self):
        try:
            self.search_entry.focus_set()
            self.search_entry.delete(0, "end")
        except Exception:
            pass

    def _schedule_chat_reorder(self):
        try:
            if hasattr(self, '_reorder_timer') and self._reorder_timer:
                try:
                    self.after_cancel(self._reorder_timer)
                except Exception:
                    pass
            self._reorder_timer = self.after(1200, self._chat_reorder_tick)
        except Exception:
            pass

    def _chat_reorder_tick(self):
        """Re-sort chat list rows by last_timestamp, only if order changed."""
        try:
            items = self._build_chat_items()
            ordered = [i[0] for i in items]
            current = list(self._chat_rows.keys())
            if ordered == current:
                return
            # Forget all rows
            for cid in current:
                refs = self._chat_rows.get(cid)
                if refs:
                    refs["frame"].pack_forget()
                    refs["sep"].pack_forget()
            # Re-pack in new order (preserving separator positions)
            for cid in ordered:
                refs = self._chat_rows.get(cid)
                if refs:
                    refs["frame"].pack(fill="x")
                    refs["sep"].pack(fill="x")
            self._filter_chats()
        except Exception:
            pass

    def _select_chat(self, chat_id: int):
        self.selected_chat_id = chat_id
        d = self.chat_map.get(chat_id, {})
        self.selected_chat_name = d.get("name", "Unknown")

        if chat_id in self.chat_map:
            self.chat_map[chat_id]["unread_count"] = 0
        for d in self.telegram_dialogs:
            if d["id"] == chat_id:
                d["unread_count"] = 0
                break

        self._build_chat_view()
        self.chat_title.configure(text=self.selected_chat_name)
        self._update_chat_status_label(chat_id)
        self._display_client_list()
        self._update_badge()
        self._show_loading_messages()

        if self.current_worker and self.current_worker.service.is_connected:
            self.current_worker.mark_as_read(chat_id)

            def on_result(messages, req_id=chat_id):
                self._hide_loading_messages()
                if self.selected_chat_id == req_id:
                    self._safe_after(0, self._display_messages, messages)
            self.current_worker.get_messages(chat_id, on_result)
            self.current_worker.get_user_status(chat_id, lambda s, cid=chat_id: self._safe_after(0, self._update_status_text, cid, s))
        else:
            self._hide_loading_messages()

    def _update_chat_status_label(self, chat_id: int):
        self.chat_status_lbl.configure(text="\u23f3  loading\u2026", text_color=TEXT_MUTED)
        if self.current_worker and self.current_worker.service.is_connected:
            self.current_worker.get_user_status(chat_id, lambda s, cid=chat_id: self._safe_after(0, self._update_status_text, cid, s))
        else:
            self.chat_status_lbl.configure(text="offline", text_color=TEXT_SECONDARY)

    def _update_status_text(self, chat_id: int, status_text: str):
        if chat_id != self.selected_chat_id or not hasattr(self, "chat_status_lbl"):
            return
        try:
            if status_text == "online":
                self.chat_status_lbl.configure(text="\u25cf  online", text_color=GREEN)
            elif status_text.startswith("last seen"):
                self.chat_status_lbl.configure(text=status_text, text_color=TEXT_SECONDARY)
            elif status_text in ("recently", "within_week", "within_month"):
                labels = {"recently": "last seen recently", "within_week": "last seen this week", "within_month": "last seen this month"}
                self.chat_status_lbl.configure(text=labels.get(status_text, status_text), text_color=TEXT_SECONDARY)
            else:
                self.chat_status_lbl.configure(text=status_text, text_color=TEXT_SECONDARY)
        except Exception:
            pass

    # ── MESSAGES ────────────────────────────────────────────────────

    def _display_messages(self, messages: list[dict]):
        try:
            self._hide_loading_messages()
            try:
                exists = self._msg_inner.winfo_exists()
            except Exception:
                return
            if not exists:
                return
            error_msgs = [m for m in messages if "error" in m]
            regular_msgs = [m for m in messages if "error" not in m]
            self.messages_cache[self.selected_chat_id] = regular_msgs

            for w in self._msg_inner.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

            if error_msgs:
                err = error_msgs[0]["error"]
                ctk.CTkLabel(self._msg_inner, text=err, font=(FONT_FAMILY, 12),
                             text_color=TEXT_SECONDARY, wraplength=400).pack(pady=40)

            if not regular_msgs and not error_msgs:
                self._show_empty_messages()
                return

            prev_date = None
            for m in reversed(regular_msgs):
                raw_date = m.get("date", "")
                try:
                    dt = datetime.fromisoformat(raw_date)
                    date_str = dt.strftime("%b %d, %Y")
                    time_str = dt.strftime("%H:%M")
                except Exception:
                    date_str = time_str = ""
                if date_str and date_str != prev_date:
                    self._add_date_sep(date_str)
                    prev_date = date_str
                self._add_bubble(m, time_str)

            self._safe_after(20, self._scroll_bottom)
        except Exception:
            pass

    def _scroll_bottom(self):
        try:
            self.msg_container._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _add_date_sep(self, text: str):
        try:
            exists = self._msg_inner.winfo_exists()
        except Exception:
            return
        if not exists:
            return
        f = ctk.CTkFrame(self._msg_inner, fg_color="transparent")
        f.pack(fill="x", pady=(10, 6))
        sep_bg = ctk.CTkFrame(f, fg_color="#DAE0E5", corner_radius=10)
        sep_bg.pack(padx=4, pady=2)
        ctk.CTkLabel(sep_bg, text=f"  {text}  ", font=(FONT_FAMILY, 11, "bold"),
                     text_color=TEXT_MUTED).pack()

    def _add_bubble(self, m: dict, time_str: str):
        try:
            try:
                inner_exists = self._msg_inner.winfo_exists()
            except Exception:
                return
            if not inner_exists:
                return
            is_out = m.get("is_outgoing", False)
            text = m.get("text", "") or ""
            sender = m.get("sender_name", "")
            media = m.get("media")
            status = m.get("status")
            reply_to = m.get("reply_to")
            is_call = m.get("is_call", False)

            bubble_bg = OUTGOING_BG if is_out else INCOMING_BG
            text_color = TEXT_PRIMARY
            sec_color = CHECK_SENT if is_out else TEXT_MUTED

            container = ctk.CTkFrame(self._msg_inner, fg_color="transparent")
            container.pack(fill="x", pady=(1, 0), anchor="e" if is_out else "w")

            pad_large = 72 if is_out else 8
            pad_small = 8 if is_out else 72

            if not is_out and sender:
                name_lbl = ctk.CTkLabel(container, text=sender, font=(FONT_FAMILY, FONT_SIZE_TIME + 1, "bold"),
                                        text_color=PRIMARY_BLUE, anchor="w")
                name_lbl.pack(fill="x", padx=(pad_large + 6, pad_small), pady=(4, 0))

            bubble = ctk.CTkFrame(container, fg_color=bubble_bg, corner_radius=BUBBLE_RADIUS)
            if not is_out:
                bubble.configure(border_width=1, border_color="#E5E5E5")
            bubble.pack(side="right" if is_out else "left",
                        padx=(pad_large, pad_small), pady=(2, 3))

            if is_call:
                call_icon = m.get("call_icon", "\U0001f4de")
                call_label = m.get("call_label", "Call")
                cf = ctk.CTkFrame(bubble, fg_color="transparent")
                cf.pack(fill="x", padx=10, pady=(7, 2))
                ctk.CTkLabel(cf, text=call_icon, font=(FONT_FAMILY, 18),
                             text_color=text_color).pack(side="left", padx=(0, 6))
                ctk.CTkLabel(cf, text=call_label, font=(FONT_FAMILY, FONT_SIZE_MSG),
                             text_color=text_color).pack(side="left")
                bot = ctk.CTkFrame(bubble, fg_color="transparent")
                bot.pack(fill="x", padx=10, pady=(0, 5))
                if time_str:
                    ctk.CTkLabel(bot, text=time_str, font=(FONT_FAMILY, FONT_SIZE_TIME),
                                 text_color=sec_color).pack(side="left")
                if is_out:
                    ck = "\U0001f514" if status == "read" else "\U0001f515"
                    ctk.CTkLabel(bot, text=ck, font=(FONT_FAMILY, FONT_SIZE_TIME),
                                 text_color=CHECK_READ if status == "read" else sec_color).pack(side="left", padx=(3, 0))
                return

            if reply_to:
                rf = ctk.CTkFrame(bubble, fg_color="transparent")
                rf.pack(fill="x", padx=8, pady=(5, 1))
                bar = ctk.CTkFrame(rf, fg_color=REPLY_ACCENT, width=3, corner_radius=1)
                bar.pack(side="left", fill="y", padx=(0, 5))
                bar.pack_propagate(False)
                ri = ctk.CTkFrame(rf, fg_color="transparent")
                ri.pack(side="left", fill="x", expand=True)
                ctk.CTkLabel(ri, text=reply_to.get("sender", ""), font=(FONT_FAMILY, FONT_SIZE_TIME + 1, "bold"),
                             text_color=REPLY_ACCENT, anchor="w").pack(fill="x")
                ctk.CTkLabel(ri, text=reply_to.get("text", ""), font=(FONT_FAMILY, FONT_SIZE_TIME + 1),
                             text_color=TEXT_SECONDARY, anchor="w", wraplength=280).pack(fill="x")

            if media:
                self._add_media_row(bubble, media, (6, 0))

            if text:
                ctk.CTkLabel(bubble, text=text, font=(FONT_FAMILY, FONT_SIZE_MSG), text_color=text_color,
                             wraplength=380, anchor="w", justify="left").pack(fill="x", padx=8, pady=(5, 2))

            bot = ctk.CTkFrame(bubble, fg_color="transparent")
            bot.pack(fill="x", padx=8, pady=(0, 4))

            if time_str:
                ctk.CTkLabel(bot, text=time_str, font=(FONT_FAMILY, FONT_SIZE_TIME),
                             text_color=sec_color).pack(side="left")

            if is_out:
                ck = "\U0001f514" if status == "read" else "\U0001f515"
                clr = CHECK_READ if status == "read" else sec_color
                ctk.CTkLabel(bot, text=ck, font=(FONT_FAMILY, FONT_SIZE_TIME),
                             text_color=clr).pack(side="left", padx=(3, 0))
        except Exception:
            pass

    def _add_media_row(self, parent, media: dict, pad_x):
        mtype = media.get("type", "document")
        fpath = media.get("file_path") or ""
        fname = media.get("file_name") or "file"
        fsize = media.get("file_size") or 0

        if mtype in ("photo", "sticker") and fpath and os.path.isfile(fpath):
            try:
                img = Image.open(fpath)
                img.thumbnail((280, 280), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self._ctkimgs.append(ctk_img)
                lbl = ctk.CTkLabel(parent, image=ctk_img, text="", fg_color="transparent", corner_radius=6)
                lbl.pack(padx=pad_x, pady=2)
                lbl.bind("<Button-1>", lambda e, p=fpath: self._open_file(p))
                return
            except Exception:
                pass

        # Audio message bubble
        if mtype in ("audio", "voice"):
            dur = media.get("duration", 0)
            dur_str = f"{dur//60}:{dur%60:02d}" if dur else "0:00"
            audio_frame = ctk.CTkFrame(parent, fg_color="transparent")
            audio_frame.pack(fill="x", padx=8, pady=4)

            play_btn = ctk.CTkButton(audio_frame, text="\u25b6", width=36, height=36,
                                      fg_color=PRIMARY_BLUE, hover_color=ACCENT_BLUE,
                                      corner_radius=18, font=(FONT_FAMILY, 14),
                                      text_color=SIDEBAR_BG)
            play_btn.pack(side="left")

            # Animated waveform visual
            wave_frame = ctk.CTkFrame(audio_frame, fg_color="transparent")
            wave_frame.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)
            heights = [6, 12, 8, 16, 10, 14, 6, 18, 12, 8, 14, 10]
            bars = []
            for h in heights:
                bar = ctk.CTkFrame(wave_frame, fg_color=ACCENT_BLUE, width=2, height=h, corner_radius=1)
                bar.pack(side="left", padx=1)
                bar.pack_propagate(False)
                bars.append(bar)

            # Pulse animation on play
            def _animate_wave():
                try:
                    import random
                    for b in bars:
                        nh = random.randint(4, 22)
                        b.configure(height=nh)
                except Exception:
                    pass

            play_btn.configure(command=lambda: _animate_wave())

            ctk.CTkLabel(audio_frame, text=dur_str, font=(FONT_FAMILY, 11),
                         text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 2))
            return

        # File/Document bubble
        if mtype == "document":
            doc_frame = ctk.CTkFrame(parent, fg_color="transparent")
            doc_frame.pack(fill="x", padx=6, pady=4)

            icon_frame = ctk.CTkFrame(doc_frame, fg_color=ACCENT_BLUE, width=36, height=36,
                                       corner_radius=18)
            icon_frame.pack(side="left")
            icon_frame.pack_propagate(False)
            ctk.CTkLabel(icon_frame, text="\u2b07", font=(FONT_FAMILY, 16),
                         text_color=SIDEBAR_BG).place(relx=0.5, rely=0.5, anchor="center")

            doc_info = ctk.CTkFrame(doc_frame, fg_color="transparent")
            doc_info.pack(side="left", fill="x", expand=True, padx=(8, 0))
            ctk.CTkLabel(doc_info, text=fname, font=(FONT_FAMILY, 12, "bold"),
                         text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
            size_str = f"{fsize//1024} KB" if fsize else "0 KB"
            ctk.CTkLabel(doc_info, text=size_str, font=(FONT_FAMILY, 10),
                         text_color=TEXT_SECONDARY, anchor="w").pack(fill="x")

            doc_frame.bind("<Button-1>", lambda e, p=fpath: self._open_file(p) if p else None)
            return

        # Generic media fallback
        icons = {"video": "\U0001f3ac", "sticker": "\U0001f642"}
        icon = icons.get(mtype, "\U0001f4c4")
        dur = media.get("duration", 0)
        dur_str = f" {dur//60}:{dur%60:02d}" if dur else ""
        size_str = f" ({fsize//1024} KB)" if fsize else ""
        label = f"{icon}  {fname}{dur_str}{size_str}"

        lnk = ctk.CTkButton(parent, text=label, font=(FONT_FAMILY, 12),
                             fg_color="transparent", hover_color=HOVER_ROW,
                             text_color=PRIMARY_BLUE, anchor="w", corner_radius=6,
                             command=lambda p=fpath: self._open_file(p) if p else None)
        lnk.pack(fill="x", padx=pad_x, pady=1)

    def _open_file(self, path):
        if not path or not os.path.isfile(path):
            return
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    # ── SEND / RECEIVE ──────────────────────────────────────────────

    def _send_file_dialog(self):
        if not self.selected_chat_id or not self.current_worker or not self.current_worker.service.is_connected:
            return
        path = filedialog.askopenfilename(title="Select file to send")
        if path:
            self._show_progress_overlay("Sending file\u2026")
            def do_send():
                try:
                    self.current_worker.send_file(self.selected_chat_id, path)
                    name = os.path.basename(path)
                    self.after(0, lambda: self._add_local_bubble(f"\U0001f4c4 {name}", is_out=True))
                except Exception:
                    pass
                self.after(0, self._hide_progress_overlay)
            threading.Thread(target=do_send, daemon=True).start()

    def _toggle_voice_recording(self):
        if not self.selected_chat_id or not self.current_worker or not self.current_worker.service.is_connected:
            return
        if getattr(self, '_voice_recording', False):
            self._stop_voice_recording()
        else:
            self._start_voice_recording()

    def _start_voice_recording(self):
        try:
            import sounddevice as sd
            import soundfile as sf
            import numpy as np

            self._voice_recording = True
            self._voice_data = []
            self._voice_record_start = datetime.now()
            self.mic_btn.configure(text="\u23f9", fg_color="#E53935", text_color=SIDEBAR_BG)

            def callback(indata, frames, time_info, status):
                try:
                    if self._voice_recording:
                        self._voice_data.append(indata.copy())
                except Exception:
                    pass

            self._voice_stream = sd.InputStream(samplerate=16000, channels=1,
                                                  callback=callback)
            self._voice_stream.start()
            self._safe_after(100, self._flash_mic)
            self._safe_after(500, self._update_recording_duration)

            def wait_and_check():
                import time
                while self._voice_recording:
                    time.sleep(0.1)
            self._voice_thread = threading.Thread(target=wait_and_check, daemon=True)
            self._voice_thread.start()
        except ImportError:
            messagebox.showinfo("Voice", "Voice recording requires:\n"
                                "  pip install sounddevice soundfile numpy\n\n"
                                "Or rebuild the EXE with build.bat after install.")
        except Exception:
            self._voice_recording = False
            self.mic_btn.configure(text="\U0001f3a4", fg_color="transparent", text_color=TEXT_PRIMARY)

    def _update_recording_duration(self):
        try:
            if getattr(self, '_voice_recording', False) and hasattr(self, 'chat_status_lbl') and self.chat_status_lbl.winfo_exists():
                elapsed = int((datetime.now() - self._voice_record_start).total_seconds())
                m, s = divmod(elapsed, 60)
                self.chat_status_lbl.configure(text=f"\u23f9  Recording {m:02d}:{s:02d}")
                self._safe_after(1000, self._update_recording_duration)
        except Exception:
            pass

    def _flash_mic(self):
        try:
            if getattr(self, '_voice_recording', False) and self.mic_btn.winfo_exists():
                cur = self.mic_btn.cget("text")
                self.mic_btn.configure(text="\u23f9" if cur == "\u25cf" else "\u25cf")
                self._safe_after(600, self._flash_mic)
        except Exception:
            pass

    def _stop_voice_recording(self):
        try:
            if self._voice_stream:
                try:
                    self._voice_stream.stop()
                    self._voice_stream.close()
                except Exception:
                    pass
                self._voice_stream = None
        except Exception:
            pass
        self._voice_recording = False
        self._voice_thread = None
        self.mic_btn.configure(text="\U0001f3a4", fg_color="transparent", text_color=TEXT_PRIMARY)
        # Reset status label
        if self.selected_chat_id:
            self._update_chat_status_label(self.selected_chat_id)

        if not self._voice_data:
            return

        try:
            import numpy as np
            import soundfile as sf

            data = np.concatenate(self._voice_data, axis=0)
            path = os.path.join("downloads", f"voice_{int(datetime.now().timestamp())}.ogg")
            os.makedirs("downloads", exist_ok=True)
            sf.write(path, data, 16000)

            if self.current_worker and self.current_worker.service.is_connected:
                self.current_worker.send_file(self.selected_chat_id, path)
                self._add_local_bubble("🎤 Voice message", is_out=True)
            self._voice_data = []
        except Exception as e:
            self._voice_data = []
            messagebox.showerror("Voice", f"Failed to save voice: {e}")

    _EMOJIS = ["😊", "😂", "😍", "🤔", "👍", "❤️", "🎉", "🔥",
               "😢", "😡", "😎", "🙏", "💪", "✨", "🌟", "⭐",
               "📎", "📄", "📷", "🎵", "🔊", "📌", "💡", "❓"]

    def _toggle_emoji_picker(self):
        if hasattr(self, '_emoji_window') and self._emoji_window and self._emoji_window.winfo_exists():
            self._emoji_window.destroy()
            self._emoji_window = None
            return
        self._emoji_window = Toplevel(self)
        self._emoji_window.title("")
        self._emoji_window.overrideredirect(True)
        self._emoji_window.configure(bg=DIVIDER)
        self._emoji_window.attributes("-topmost", True)
        f = ctk.CTkFrame(self._emoji_window, fg_color=SIDEBAR_BG, corner_radius=10,
                         border_width=1, border_color=INPUT_BORDER)
        f.pack(padx=6, pady=6)
        # Title bar
        title_f = ctk.CTkFrame(f, fg_color="transparent")
        title_f.pack(fill="x", padx=6, pady=(6, 2))
        ctk.CTkLabel(title_f, text="Emoji", font=(FONT_FAMILY, 11, "bold"),
                     text_color=TEXT_MUTED, anchor="w").pack(side="left")
        close_b = ctk.CTkButton(title_f, text="\u2716", width=24, height=24, corner_radius=12,
                                 fg_color="transparent", hover_color=HOVER_ROW,
                                 text_color=TEXT_MUTED, font=(FONT_FAMILY, 12),
                                 command=lambda: self._close_emoji_picker())
        close_b.pack(side="right")
        # Search bar
        search_emoji = ctk.CTkEntry(f, placeholder_text="Search emoji\u2026", height=30,
                                     fg_color=SEARCH_BG, border_width=0, corner_radius=6,
                                     font=(FONT_FAMILY, 11), text_color=TEXT_PRIMARY,
                                     placeholder_text_color=TEXT_MUTED)
        search_emoji.pack(fill="x", padx=6, pady=(0, 4))
        # Emoji grid
        grid_f = ctk.CTkFrame(f, fg_color="transparent")
        grid_f.pack(padx=4, pady=(0, 4))
        row_f = None
        for i, em in enumerate(self._EMOJIS):
            if i % 6 == 0:
                row_f = ctk.CTkFrame(grid_f, fg_color="transparent")
                row_f.pack(fill="x")
            btn = ctk.CTkButton(row_f, text=em, width=38, height=38, corner_radius=8,
                                 fg_color="transparent", hover_color=HOVER_ROW,
                                 font=(FONT_FAMILY, 18),
                                 command=lambda e=em: self._insert_emoji(e))
            btn.pack(side="left", padx=1, pady=1)
        # Close on focus loss
        self._emoji_window.bind("<FocusOut>", lambda e: self._safe_after(100, self._close_emoji_picker))
        self._position_emoji_picker()

    def _close_emoji_picker(self):
        try:
            if hasattr(self, '_emoji_window') and self._emoji_window and self._emoji_window.winfo_exists():
                self._emoji_window.destroy()
        except Exception:
            pass
        self._emoji_window = None

    def _position_emoji_picker(self):
        try:
            x = self.winfo_x() + self.winfo_width() - 320
            y = self.winfo_y() + self.winfo_height() - 240
            self._emoji_window.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _insert_emoji(self, em):
        try:
            cur = self.message_entry.get()
            self.message_entry.delete(0, "end")
            self.message_entry.insert(0, cur + em)
            self.message_entry.focus_set()
        except Exception:
            pass

    def _add_local_bubble(self, text, is_out=True):
        try:
            if hasattr(self, "_msg_inner") and self._msg_inner.winfo_exists():
                now = datetime.now().strftime("%H:%M")
                self._add_bubble({
                    "is_outgoing": is_out,
                    "text": text,
                    "status": "sent",
                    "sender_name": "",
                }, now)
                self._safe_after(20, self._scroll_bottom)
        except Exception:
            pass

    def _send_message(self):
        text = self.message_entry.get().strip()
        if not text or not self.selected_chat_id:
            return
        if self.current_worker and self.current_worker.service.is_connected:
            self.current_worker.send_message(self.selected_chat_id, text)
            self.message_entry.delete(0, "end")
            self._add_local_bubble(text, is_out=True)

    def _show_toast(self, title, message, duration=3000):
        try:
            try:
                from plyer import notification
                notification.notify(title=title, message=message, timeout=duration // 1000)
                return
            except Exception:
                pass
            toast = ctk.CTkToplevel(self)
            toast.title("")
            toast.geometry("320x80")
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            toast.configure(fg_color=SIDEBAR_BG)
            px = self.winfo_x() + self.winfo_width() - 340
            py = self.winfo_y() + 60
            toast.geometry(f"320x80+{px}+{py}")
            # Card with border
            card = ctk.CTkFrame(toast, fg_color=SIDEBAR_BG, corner_radius=10,
                                border_width=1, border_color=INPUT_BORDER)
            card.pack(fill="both", expand=True, padx=2, pady=2)
            ctk.CTkLabel(card, text=title, font=(FONT_FAMILY, 12, "bold"), text_color=PRIMARY_BLUE,
                         anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            ctk.CTkLabel(card, text=message, font=(FONT_FAMILY, 11), text_color=TEXT_SECONDARY,
                         anchor="w", wraplength=280).pack(fill="x", padx=12, pady=(2, 8))
            toast.after(duration, toast.destroy)
        except Exception:
            pass

    def _media_preview_label(self, media):
        if not media:
            return ""
        mtype = media.get("type", "")
        labels = {
            "photo": "\U0001f4f7 Photo",
            "sticker": "\U0001f4f7 Sticker",
            "voice": "\U0001f3a4 Voice message",
            "audio": "\U0001f3b5 Audio",
            "video": "\U0001f3ac Video",
            "document": "\U0001f4c4 Document",
        }
        return labels.get(mtype, "\U0001f4c4 Attachment")

    def _on_message(self, msg: dict):
        try:
            chat_id = msg.get("chat_id")
            if chat_id is None:
                return
            text = msg.get("text", "")
            sender = msg.get("sender_name", "")
            is_out = msg.get("is_outgoing", False)
            media = msg.get("media")
            preview = text[:60] if text else self._media_preview_label(media)
            with self._lock:
                chat_name = self.chat_map.get(chat_id, {}).get("name", sender) or sender or f"User {chat_id}"
                self.messages_cache.setdefault(chat_id, [])

                msg_id = msg.get("id")
                if msg_id:
                    for existing in self.messages_cache[chat_id]:
                        if existing.get("id") == msg_id:
                            if msg.get("status"):
                                existing["status"] = msg["status"]
                            if chat_id == self.selected_chat_id and hasattr(self, "_msg_inner"):
                                try:
                                    self._display_messages(self.messages_cache[chat_id])
                                except Exception:
                                    pass
                            return

                self.messages_cache[chat_id].append(msg)
                now_ts = datetime.now().timestamp()
                if chat_id not in self.chat_map:
                    self.chat_map[chat_id] = {
                        "name": chat_name,
                        "unread_count": 0,
                        "last_message": preview,
                        "last_timestamp": now_ts,
                        "client": None,
                    }
                    if not any(d.get("id") == chat_id for d in self.telegram_dialogs):
                        self.telegram_dialogs.append({
                            "id": chat_id,
                            "name": chat_name,
                            "unread_count": 0 if is_out else 1,
                            "last_message": preview,
                            "last_timestamp": now_ts,
                            "is_pinned": False,
                        })

                if preview:
                    self.chat_map[chat_id]["last_message"] = preview
                    self.chat_map[chat_id]["last_timestamp"] = now_ts
                if not is_out:
                    self.chat_map[chat_id]["unread_count"] = self.chat_map[chat_id].get("unread_count", 0) + 1
                for d in self.telegram_dialogs:
                    if d["id"] == chat_id:
                        if preview:
                            d["last_message"] = preview
                            d["last_timestamp"] = now_ts
                        if not is_out:
                            d["unread_count"] = d.get("unread_count", 0) + 1
                        break

                row_updated = False
                if chat_id in getattr(self, '_chat_rows', {}):
                    d = self.chat_map.get(chat_id, {})
                    row_updated = self._update_chat_row(
                        chat_id, d.get("name", chat_name),
                        d.get("unread_count", 0),
                        d.get("last_message", ""),
                        d.get("last_timestamp", 0.0),
                        d.get("client"),
                    )
                needs_rebuild = chat_id not in getattr(self, '_chat_rows', {})
            if not is_out and chat_id != self.selected_chat_id and preview:
                self._safe_after(0, self._show_toast, f"Message from {chat_name}", preview)
                _play_notification_async()

            if chat_id == self.selected_chat_id and hasattr(self, "_msg_inner"):
                try:
                    now = datetime.now().strftime("%H:%M")
                    self._add_bubble(msg, now)
                    self._safe_after(20, self._scroll_bottom)
                except Exception:
                    pass

            if needs_rebuild:
                self._safe_after(50, self._display_client_list)
            elif not row_updated:
                self._schedule_chat_reorder()
        except Exception:
            pass

    def _on_read(self, data: dict):
        chat_id = data.get("chat_id")
        msg_ids = data.get("message_ids", [])
        if not chat_id or not msg_ids:
            return
        with self._lock:
            msgs = self.messages_cache.get(chat_id, [])
            changed = False
            for m in msgs:
                if m.get("id") in msg_ids and m.get("is_outgoing"):
                    m["status"] = "read"
                    changed = True
        if changed and chat_id == self.selected_chat_id and hasattr(self, "_msg_inner"):
            self._safe_after(100, lambda: self._display_messages(self.messages_cache.get(chat_id, [])))

    def _mark_selected_read(self):
        if not self.selected_chat_id or not self.current_worker:
            return
        if self.current_worker.service.is_connected:
            self.current_worker.mark_as_read(self.selected_chat_id)

    # ── CALLS ───────────────────────────────────────────────────────

    def _make_call(self, video=False):
        if not self.selected_chat_id:
            return
        if self.current_worker and self.current_worker.service.is_connected:
            self.current_worker.make_call(self.selected_chat_id, video)
            name = self.selected_chat_name
            if hasattr(self, "call_overlay") and self.call_overlay and self.call_overlay.winfo_exists():
                self.call_overlay.show_outgoing(name, video)

    def _on_call(self, data: dict):
        call_type = data.get("type", "")
        user_id = data.get("user_id")
        if not user_id:
            return
        chat_info = None
        for cid, info in self.chat_map.items():
            if cid == user_id:
                chat_info = info
                break
        chat_name = chat_info.get("name", f"User {user_id}") if chat_info else f"User {user_id}"

        if call_type == "incoming":
            is_video = data.get("video", False)
            self._show_call_overlay(chat_name, is_video, data)
            self._add_call_message(user_id, "incoming", is_video)
        elif call_type == "outgoing":
            is_video = data.get("video", False)
            self._show_call_overlay(None, is_video, data)
            self._add_call_message(user_id, "outgoing", is_video)
        elif call_type == "connected":
            if hasattr(self, "call_overlay") and self.call_overlay:
                self.call_overlay.show_connected()
        elif call_type == "discarded":
            if hasattr(self, "call_overlay") and self.call_overlay:
                self.call_overlay.show_ended()
            reason = data.get("reason", "")
            if reason == "ended":
                label = "\U0001f4de Call ended"
            elif reason == "rejected":
                label = "\U0001f4de Call rejected"
            else:
                label = "\U0001f4de Missed call"
            self._add_call_message(user_id, reason or "missed", False)
            self._update_call_preview(user_id, label)

    def _add_call_message(self, chat_id: int, call_type: str, is_video: bool):
        call_icons = {
            "incoming": "\U0001f4de",
            "outgoing": "\U0001f4de",
            "ended": "\U0001f4de",
            "rejected": "\U0001f4de",
            "missed": "\U0001f4de",
        }
        call_labels = {
            "incoming": "Incoming call",
            "outgoing": "Outgoing call",
            "ended": "Call ended",
            "rejected": "Call rejected",
            "missed": "Missed call",
        }
        icon = call_icons.get(call_type, "\U0001f4de")
        label = call_labels.get(call_type, "Call")
        if is_video:
            label = "Video " + label.lower()
        is_out = call_type == "outgoing"
        now = datetime.now()

        msg_entry = {
            "id": f"call_{chat_id}_{int(now.timestamp())}",
            "chat_id": chat_id,
            "text": "",
            "date": now.isoformat(),
            "is_outgoing": is_out,
            "is_call": True,
            "call_icon": icon,
            "call_label": label,
            "sender_name": "",
        }
        with self._lock:
            self.messages_cache.setdefault(chat_id, [])
            self.messages_cache[chat_id].append(msg_entry)
            self.chat_map.setdefault(chat_id, {})["last_message"] = f"{icon} {label}"
            self.chat_map[chat_id]["last_timestamp"] = now.timestamp()

        if chat_id == self.selected_chat_id and hasattr(self, "_msg_inner"):
            try:
                time_str = now.strftime("%H:%M")
                self._add_bubble(msg_entry, time_str)
                self._safe_after(20, self._scroll_bottom)
            except Exception:
                pass

    def _update_call_preview(self, chat_id, label):
        if not chat_id:
            return
        now_ts = datetime.now().timestamp()
        if chat_id in self.chat_map:
            self.chat_map[chat_id]["last_message"] = label
            self.chat_map[chat_id]["last_timestamp"] = now_ts
        for d in self.telegram_dialogs:
            if d["id"] == chat_id:
                d["last_message"] = label
                d["last_timestamp"] = now_ts
                break
        try:
            d = self.chat_map.get(chat_id, {})
            self._update_chat_row(
                chat_id,
                d.get("name", ""),
                d.get("unread_count", 0),
                label,
                now_ts,
                d.get("client"),
            )
            self._schedule_chat_reorder()
        except Exception:
            pass

    def _show_call_overlay(self, caller_name, is_video, data):
        if not hasattr(self, "call_overlay") or not self.call_overlay or not self.call_overlay.winfo_exists():
            self.call_overlay = CallOverlay(self, self.current_worker)
        if data.get("type") == "incoming":
            self.call_overlay.show_incoming(caller_name, is_video, data)
        else:
            self.call_overlay.show_outgoing(caller_name or "Unknown", is_video)

    # ── AUTH ────────────────────────────────────────────────────────

    def _handle_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            self.login_status.configure(text="Email and password are required")
            return
        self.login_btn.configure(state="disabled", text="Signing in\u2026")
        self.login_status.configure(text="")

        def do_login():
            try:
                self.supabase.sign_in(email, password)
                au = self.supabase.get_current_user()
                user = None
                if au and au.user:
                    user = self.supabase.get_user_by_id(au.user.id)
                self.after(0, self._on_login_success, user)
            except Exception as e:
                self.after(0, self._on_login_fail, str(e))

        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_success(self, user):
        if user:
            self.current_user = user
            self._save_auth_session()
            self.login_frame.pack_forget()
            self.main_frame.pack(fill="both", expand=True)
            self._load_assignments()
        else:
            self.login_btn.configure(state="normal", text="Sign In")
            self.login_status.configure(text="User profile not found")

    def _on_login_fail(self, error):
        self.login_btn.configure(state="normal", text="Sign In")
        self.login_status.configure(text=f"Login failed: {error}")

    # ── ASSIGNMENTS & CONNECTION ────────────────────────────────────

    def _load_assignments(self):
        if not self.current_user:
            return
        self._show_loading_sidebar()
        def do_load():
            try:
                assignments = self.supabase.get_staff_assignments(self.current_user.id)
                for a in assignments:
                    worker = TelegramWorker(a, self)
                    worker.on_connected = self._on_connected
                    worker.on_disconnected = self._on_disconnected
                    worker.on_message = self._on_message
                    worker.on_read = self._on_read
                    worker.on_call = self._on_call
                    self.workers[a.gateway_number] = worker
                self.after(0, self._auto_connect_workers)
            except Exception:
                self.after(0, self._hide_loading_sidebar)
        threading.Thread(target=do_load, daemon=True).start()

    def _save_auth_session(self):
        try:
            session = self.supabase.client.auth.get_session()
            if session and hasattr(session, 'access_token'):
                AUTH_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
                AUTH_SESSION_FILE.write_text(json.dumps({
                    "access_token": session.access_token,
                    "refresh_token": getattr(session, 'refresh_token', ''),
                }))
        except Exception:
            pass

    def _auto_connect_workers(self):
        self._hide_loading_sidebar()
        if not self.workers:
            self._show_empty_chat("No gateway assignments found")
            return
        for gw, worker in self.workers.items():
            if worker.service.has_session:
                self.current_worker = worker
                self.connect_btn.configure(text="Connecting\u2026", state="disabled")
                worker.start_and_connect(lambda: self.after(0, self._on_connect_done))
                break
        else:
            self.connect_btn.pack(fill="x")

    def _on_connect_done(self):
        self.connect_btn.configure(text="Connect to Telegram", state="normal")

    def _connect_account(self):
        for gw, worker in self.workers.items():
            self.current_worker = worker
            if worker.service.has_session:
                self.connect_btn.configure(text="Connecting\u2026", state="disabled")
                worker.start_and_connect(lambda: self.after(0, self._on_connect_done))
            else:
                ConnectDialog(self, worker)
            break

    def _on_connected(self):
        self.status_dot.configure(text="\u25cf", text_color=GREEN, font=(FONT_FAMILY, 14))
        self.connect_btn.pack_forget()
        self._show_loading_sidebar()
        self._load_assigned_clients()
        self.current_worker.get_user_dialogs(self._on_dialogs_loaded)
        self._update_badge()

    def _on_disconnected(self):
        self.status_dot.configure(text="\u25cf", text_color=DANGER, font=(FONT_FAMILY, 14))
        self.connect_btn.pack(fill="x")
        self._show_welcome()
        self._show_toast("Disconnected", "Telegram connection lost. Reconnect to continue.")

    def _load_assigned_clients(self):
        if not self.current_user or not self.current_worker:
            return
        gw = self.current_worker.assignment.gateway_number
        office_id = self.current_user.office_id if self.current_user else None
        if not office_id:
            self.assigned_clients = []
            self._display_client_list()
            return
        try:
            clients = self.supabase.get_clients_by_office(office_id, gw)
        except Exception:
            clients = []
        self.assigned_clients = clients
        self._display_client_list()

    def _on_dialogs_loaded(self, dialogs: list[dict]):
        self.telegram_dialogs = dialogs
        self._hide_loading_sidebar()
        try:
            self._display_client_list()
        except Exception:
            pass

    def _load_contacts(self):
        if not self.current_worker or not self.current_worker.service.is_connected:
            return
        def on_result(contacts):
            pass
        self.current_worker.get_contacts(on_result)


class ConnectDialog(ctk.CTkToplevel):
    def __init__(self, parent, worker):
        super().__init__(parent)
        self.worker = worker
        self.title("Connect to Telegram")
        self.geometry("480x560")
        self.resizable(False, False)
        self.configure(fg_color=SIDEBAR_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.grab_set()

        self.tabview = ctk.CTkTabview(self, fg_color=SIDEBAR_BG,
                                        segmented_button_fg_color=SEARCH_BG,
                                        segmented_button_selected_color=PRIMARY_BLUE,
                                        segmented_button_selected_hover_color=ACCENT_BLUE)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=12)
        self.tab_qr = self.tabview.add("QR Code")
        self.tab_phone = self.tabview.add("Phone")
        self._setup_qr_tab()
        self._setup_phone_tab()
        self._closed = False
        self.after(100, self._start_qr_flow)

    def _exists(self):
        try:
            return self.winfo_exists()
        except Exception:
            return False

    def _safe_configure(self, widget, **kwargs):
        if self._closed or not self._exists():
            return
        try:
            widget.configure(**kwargs)
        except Exception:
            pass

    def _setup_qr_tab(self):
        tab = self.tab_qr
        ctk.CTkLabel(tab, text="Scan QR Code", font=(FONT_FAMILY, 16, "bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(20, 5))
        ctk.CTkLabel(tab, text="Open Telegram on your phone and scan",
                     font=(FONT_FAMILY, 12), text_color=TEXT_SECONDARY).pack(pady=(0, 15))
        self.qr_frame = ctk.CTkFrame(tab, fg_color=SIDEBAR_BG, corner_radius=10, width=280, height=280,
                                       border_width=1, border_color=INPUT_BORDER)
        self.qr_frame.pack(padx=50, pady=5)
        self.qr_frame.pack_propagate(False)
        self.qr_label = ctk.CTkLabel(self.qr_frame, text="Generating\u2026",
                                      font=(FONT_FAMILY, 13), text_color=TEXT_SECONDARY)
        self.qr_label.place(relx=0.5, rely=0.5, anchor="center")
        self.qr_status = ctk.CTkLabel(tab, text="Waiting for scan\u2026",
                                       font=(FONT_FAMILY, 12), text_color=PRIMARY_BLUE)
        self.qr_status.pack(pady=(15, 5))

    def _setup_phone_tab(self):
        tab = self.tab_phone
        ctk.CTkLabel(tab, text="Phone Verification", font=(FONT_FAMILY, 16, "bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(20, 5))
        ctk.CTkLabel(tab, text="Enter your phone number",
                     font=(FONT_FAMILY, 12), text_color=TEXT_SECONDARY).pack(pady=(0, 15))
        self.phone_entry = ctk.CTkEntry(tab, placeholder_text="+1 234 567 890", width=300, height=42,
                                         fg_color=SIDEBAR_BG, border_width=1, border_color=INPUT_BORDER,
                                         corner_radius=8, text_color=TEXT_PRIMARY,
                                         placeholder_text_color=TEXT_MUTED)
        self.phone_entry.pack(padx=40, pady=(0, 10))
        self.send_code_btn = ctk.CTkButton(tab, text="Send Code", command=self._send_code,
                                             width=300, height=42, fg_color=PRIMARY_BLUE,
                                             hover_color=ACCENT_BLUE, corner_radius=8,
                                             font=(FONT_FAMILY, 13, "bold"))
        self.send_code_btn.pack(padx=40, pady=(0, 5))
        self.phone_status = ctk.CTkLabel(tab, text="", font=(FONT_FAMILY, 12), text_color=DANGER)
        self.phone_status.pack(padx=40, pady=(0, 10))

        self.code_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.code_frame.pack(fill="x", padx=40, pady=(5, 0))
        self.code_frame.pack_forget()
        ctk.CTkLabel(self.code_frame, text="Verification Code:", font=(FONT_FAMILY, 12),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 4))
        self.code_entry = ctk.CTkEntry(self.code_frame, placeholder_text="12345", width=300, height=42,
                                        fg_color=SIDEBAR_BG, border_width=1, border_color=INPUT_BORDER,
                                        corner_radius=8, text_color=TEXT_PRIMARY,
                                        placeholder_text_color=TEXT_MUTED)
        self.code_entry.pack(pady=(0, 8))
        self.verify_btn = ctk.CTkButton(self.code_frame, text="Verify", command=self._verify_code,
                                         width=300, height=42, fg_color=GREEN, hover_color="#27AE60",
                                         corner_radius=8, font=(FONT_FAMILY, 13, "bold"))
        self.verify_btn.pack(pady=(0, 5))
        self.password_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.password_frame.pack(fill="x", padx=40, pady=(5, 0))
        self.password_frame.pack_forget()
        ctk.CTkLabel(self.password_frame, text="2FA Password:", font=(FONT_FAMILY, 12),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 4))
        self.password_entry = ctk.CTkEntry(self.password_frame, placeholder_text="Your 2FA password",
                                            show="\u2022", width=300, height=42,
                                            fg_color=SIDEBAR_BG, border_width=1, border_color=INPUT_BORDER,
                                            corner_radius=8, text_color=TEXT_PRIMARY,
                                            placeholder_text_color=TEXT_MUTED)
        self.password_entry.pack(pady=(0, 8))
        self.verify_pw_btn = ctk.CTkButton(self.password_frame, text="Verify Password",
                                            command=self._verify_password, width=300, height=42,
                                            fg_color=WARNING, hover_color="#E67E22",
                                            corner_radius=8, font=(FONT_FAMILY, 13, "bold"))
        self.verify_pw_btn.pack(pady=(0, 5))

    def _start_qr_flow(self):
        if self._closed:
            return
        self.worker.start_loop()
        self.worker.service.on("on_message", lambda m: self.worker.app.after(0, self.worker.on_message, m) if self.worker.on_message else None)
        self.worker.service.on("on_read", lambda d: self.worker.app.after(0, self.worker.on_read, d) if self.worker.on_read else None)
        self.worker.service.on("on_call", lambda d: self.worker.app.after(0, self.worker.on_call, d) if self.worker.on_call else None)
        self.worker.service.on("on_status_change", lambda d: self.worker.app.after(0, self.worker._on_status_change_ui, d))

        def run():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.worker.service.qr_login_flow(
                        on_url=lambda url: self.after(0, self._show_qr, url),
                        on_done=lambda ok: self.after(0, self._on_auth_success if ok else self._on_auth_fail),
                    ),
                    self.worker.loop
                )
                future.result(timeout=300)
            except Exception:
                if not self._closed:
                    self.after(0, self._on_auth_fail)
        self.worker.run_in_background(run)

    def _show_qr(self, url):
        if self._closed or not self._exists():
            return
        try:
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color=TEXT_PRIMARY, back_color="white")
            img = img.resize((250, 250), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(250, 250))
            self._safe_configure(self.qr_label, image=ctk_img, text="")
            self.qr_label.image = ctk_img
            self._safe_configure(self.qr_status, text="Scan the QR code with Telegram")
        except Exception as e:
            self._safe_configure(self.qr_status, text=f"Error: {e}")

    def _send_code(self):
        if self._closed or not self._exists():
            return
        phone = self.phone_entry.get().strip()
        if not phone:
            self._safe_configure(self.phone_status, text="Enter your phone number")
            return
        if self.worker.app.current_user:
            assignments = self.worker.app.supabase.get_staff_assignments(self.worker.app.current_user.id)
            valid_numbers = [a.phone_number for a in assignments if a.is_active]
            phone_clean = phone.replace("+", "").replace("-", "").replace(" ", "")
            matched = any(
                vn.replace("+", "").replace("-", "").replace(" ", "") == phone_clean
                for vn in valid_numbers
            )
            if not matched:
                self._safe_configure(self.phone_status,
                    text=f"Phone not assigned. Your numbers: {', '.join(valid_numbers) if valid_numbers else 'None'}"
                )
                self._safe_configure(self.send_code_btn, state="normal", text="Send Code")
                return
        self._safe_configure(self.send_code_btn, state="disabled", text="Sending\u2026")
        self._safe_configure(self.phone_status, text="")
        self.worker.start_loop()

        def run():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.worker.service.phone_request_code(phone), self.worker.loop
                )
                ok = future.result(timeout=30)
                if ok:
                    self.after(0, self._on_code_sent)
                else:
                    self.after(0, self._on_code_fail, "Failed to send code")
            except Exception as e:
                self.after(0, self._on_code_fail, str(e))
        self.worker.run_in_background(run)

    def _on_code_sent(self):
        if self._closed or not self._exists():
            return
        self._safe_configure(self.send_code_btn, state="normal", text="Send Code")
        self._safe_configure(self.phone_status, text="Code sent!", text_color=GREEN)
        try:
            if self._exists():
                self.code_frame.pack(fill="x", padx=40, pady=(5, 0))
                self.code_entry.focus_set()
        except Exception:
            pass

    def _on_code_fail(self, msg):
        if self._closed or not self._exists():
            return
        self._safe_configure(self.send_code_btn, state="normal", text="Send Code")
        self._safe_configure(self.phone_status, text=msg, text_color=DANGER)

    def _verify_code(self):
        if self._closed or not self._exists():
            return
        phone = self.phone_entry.get().strip()
        code = self.code_entry.get().strip()
        if not code:
            self._safe_configure(self.phone_status, text="Enter the verification code")
            return
        self._safe_configure(self.verify_btn, state="disabled", text="Verifying\u2026")

        def run():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.worker.service.phone_submit_code(phone, code), self.worker.loop
                )
                result = future.result(timeout=30)
                if result == "ok":
                    self.after(0, self._on_auth_success)
                elif result == "password_needed":
                    self.after(0, self._on_password_needed)
                else:
                    self.after(0, self._on_code_fail, "Invalid code")
            except Exception as e:
                self.after(0, self._on_code_fail, str(e))
            finally:
                def _restore():
                    if not self._closed and self._exists():
                        self._safe_configure(self.verify_btn, state="normal", text="Verify")
                self.after(0, _restore)
        self.worker.run_in_background(run)

    def _on_password_needed(self):
        if self._closed or not self._exists():
            return
        self._safe_configure(self.verify_btn, state="normal", text="Verify")
        self._safe_configure(self.phone_status, text="2FA enabled. Enter your password.", text_color=WARNING)
        try:
            if self._exists():
                self.password_frame.pack(fill="x", padx=40, pady=(5, 0))
                self.password_entry.focus_set()
        except Exception:
            pass

    def _verify_password(self):
        if self._closed or not self._exists():
            return
        password = self.password_entry.get().strip()
        if not password:
            self._safe_configure(self.phone_status, text="Enter your 2FA password")
            return
        self._safe_configure(self.verify_pw_btn, state="disabled", text="Verifying\u2026")

        def run():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.worker.service.phone_submit_password(password), self.worker.loop
                )
                ok = future.result(timeout=30)
                if ok:
                    self.after(0, self._on_auth_success)
                else:
                    self.after(0, self._on_code_fail, "Wrong password")
            except Exception as e:
                self.after(0, self._on_code_fail, str(e))
            finally:
                def _restore():
                    if not self._closed and self._exists():
                        self._safe_configure(self.verify_pw_btn, state="normal", text="Verify Password")
                self.after(0, _restore)
        self.worker.run_in_background(run)

    def _on_auth_success(self):
        if self._closed:
            return
        self._closed = True
        self.worker.on_connected()
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        try:
            self.master._on_connect_done()
        except Exception:
            pass

    def _on_auth_fail(self):
        if self._closed or not self._exists():
            return
        self._safe_configure(self.qr_status, text="Authentication failed. Try again.")

    def _on_close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


class CallOverlay(ctk.CTkToplevel):
    WIDTH = 420
    HEIGHT = 140
    EXPANDED_HEIGHT = 200

    def __init__(self, parent, worker):
        super().__init__(parent)
        self.parent = parent
        self.worker = worker
        self.call_data = None
        self._state = "idle"
        self._duration = 0
        self._timer_id = None
        self._fade_id = None

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=SIDEBAR_BG)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._build_ui()

    def _build_ui(self):
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)

        # Shadow/border effect
        main = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, corner_radius=12,
                            border_width=1, border_color=INPUT_BORDER)
        main.pack(fill="both", expand=True, padx=2, pady=2)

        top = ctk.CTkFrame(main, fg_color="transparent", height=32, cursor="fleur")
        top.pack(fill="x")
        top.pack_propagate(False)
        top.bind("<ButtonPress-1>", self._start_move)
        top.bind("<B1-Motion>", self._on_move)

        # Drag handle indicator
        handle = ctk.CTkFrame(top, fg_color=DIVIDER, height=3, width=30, corner_radius=2)
        handle.place(relx=0.5, rely=0.5, anchor="center")

        self.content = ctk.CTkFrame(main, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        self.icon_label = ctk.CTkLabel(self.content, text="", font=(FONT_FAMILY, 32))
        self.icon_label.pack(side="left", padx=(0, 14))

        info_f = ctk.CTkFrame(self.content, fg_color="transparent")
        info_f.pack(side="left", fill="both", expand=True)

        self.name_label = ctk.CTkLabel(info_f, text="", font=(FONT_FAMILY, 16, "bold"),
                                        text_color=TEXT_PRIMARY, anchor="w")
        self.name_label.pack(fill="x")

        self.status_label = ctk.CTkLabel(info_f, text="", font=(FONT_FAMILY, 12),
                                          text_color=TEXT_SECONDARY, anchor="w")
        self.status_label.pack(fill="x")

        self.btn_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.btn_frame.pack(side="right", padx=(8, 0))

        self.answer_btn = ctk.CTkButton(self.btn_frame, text="\u260e", command=self._answer,
                                         fg_color=GREEN, hover_color="#27AE60",
                                         width=48, height=48, corner_radius=24,
                                         font=(FONT_FAMILY, 20))
        self.end_btn = ctk.CTkButton(self.btn_frame, text="\u2716", command=self._hang_up,
                                      fg_color=DANGER, hover_color="#C0392B",
                                      width=48, height=48, corner_radius=24,
                                      font=(FONT_FAMILY, 20))

        self._center_top()

    def _center_top(self):
        try:
            px = self.parent.winfo_x()
            py = self.parent.winfo_y()
            pw = self.parent.winfo_width()
            x = px + (pw - self.WIDTH) // 2
            self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{py + 12}")
        except Exception:
            pass

    def _start_move(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_move(self, event):
        try:
            x = event.x_root - self._drag_x
            y = event.y_root - self._drag_y
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def show_incoming(self, caller_name, is_video, call_data):
        self.call_data = call_data
        self._state = "ringing"
        icon = "\U0001f4f9" if is_video else "\U0001f50a"
        call_type = "Video Call" if is_video else "Voice Call"
        self.icon_label.configure(text=icon)
        self.name_label.configure(text=caller_name)
        self.status_label.configure(text=f"\u25cf  {call_type}")
        self.answer_btn.pack(side="left", padx=4)
        self.end_btn.pack_forget()
        self.btn_frame.pack(side="right", padx=(8, 0))
        play_ringtone()
        self._show()

    def show_outgoing(self, name, is_video):
        self._state = "outgoing"
        stop_ringtone()
        icon = "\U0001f4f9" if is_video else "\U0001f50a"
        call_type = "Video Call" if is_video else "Voice Call"
        self.icon_label.configure(text=icon)
        self.name_label.configure(text=name)
        self.status_label.configure(text=f"\u23f3  {call_type}")
        self.answer_btn.pack_forget()
        self.end_btn.pack(side="left", padx=4)
        self.btn_frame.pack(side="right", padx=(8, 0))
        self._show()

    def show_connected(self):
        self._state = "connected"
        stop_ringtone()
        self._duration = 0
        self.status_label.configure(text="00:00")
        self.answer_btn.pack_forget()
        self.end_btn.pack(side="left", padx=4)
        self._tick_timer()

    def show_ended(self):
        self._state = "ended"
        stop_ringtone()
        if self._timer_id:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        dur = self._format_duration(self._duration)
        self.status_label.configure(text=f"Call ended  \u2022  {dur}")
        self.answer_btn.pack_forget()
        self.end_btn.pack_forget()
        self.btn_frame.pack_forget()
        self._safe_close(3)

    def _tick_timer(self):
        if self._state != "connected":
            return
        try:
            self.status_label.configure(text=self._format_duration(self._duration))
            self._duration += 1
            self._timer_id = self.after(1000, self._tick_timer)
        except Exception:
            pass

    def _format_duration(self, secs):
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _answer(self):
        if self.worker:
            try:
                self.worker.answer_call()
            except Exception:
                pass
        self.show_connected()

    def _hang_up(self):
        if self._state == "ringing" and self.worker:
            try:
                self.worker.reject_call()
            except Exception:
                pass
        elif self.worker:
            try:
                self.worker.end_call()
            except Exception:
                pass
        self.show_ended()

    def _show(self):
        try:
            self._center_top()
            self.deiconify()
            self.lift()
            self.focus_set()
        except Exception:
            pass

    def _safe_close(self, delay=0):
        stop_ringtone()
        def _do_close():
            try:
                self._state = "idle"
                if self._timer_id:
                    try:
                        self.after_cancel(self._timer_id)
                    except Exception:
                        pass
                    self._timer_id = None
                if self._fade_id:
                    try:
                        self.after_cancel(self._fade_id)
                    except Exception:
                        pass
                    self._fade_id = None
                try:
                    self.withdraw()
                except Exception:
                    self.destroy()
            except Exception:
                pass
        if delay > 0:
            self._fade_id = self.after(delay * 1000, _do_close)
        else:
            _do_close()

    def _close(self):
        self._hang_up()


# ── WORKER ───────────────────────────────────────────────────────────

class TelegramWorker:
    def __init__(self, assignment, app):
        self.assignment = assignment
        self.service = TelegramService(assignment)
        self.app = app
        self.on_connected = None
        self.on_disconnected = None
        self.on_message = None
        self.on_read = None
        self.on_call = None
        self.loop = None
        self._loop_thread = None

    def start_loop(self):
        if self.loop and self.loop.is_running():
            return
        self.loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_in_background(self, func):
        threading.Thread(target=func, daemon=True).start()

    def start_and_connect(self, on_connect_done=None):
        self.start_loop()
        self.service.on("on_message", lambda m: self.app.after(0, self.on_message, m) if self.on_message else None)
        self.service.on("on_read", lambda d: self.app.after(0, self.on_read, d) if self.on_read else None)
        self.service.on("on_call", lambda d: self.app.after(0, self.on_call, d) if self.on_call else None)
        self.service.on("on_status_change", lambda d: self.app.after(0, self._on_status_change_ui, d))
        self._connect_callback = on_connect_done

        def run():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.service.connect(), self.loop
                )
                success = future.result(timeout=30)
                if success and self.on_connected:
                    self.app.after(0, self.on_connected)
                if self._connect_callback:
                    self.app.after(0, self._connect_callback)
            except Exception:
                pass
                if self._connect_callback:
                    self.app.after(0, self._connect_callback)
        self.run_in_background(run)

    def _on_status_change_ui(self, data):
        user_id = data.get("user_id")
        status = data.get("status", "offline")
        if self.app.selected_chat_id == user_id:
            try:
                self.app._update_status_text(user_id, status)
            except Exception:
                pass

    def disconnect(self):
        if self.loop and self.loop.is_running():
            self.app._show_progress_overlay("Disconnecting\u2026")
            def run():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.service.disconnect(), self.loop
                    )
                    future.result(timeout=10)
                except Exception:
                    pass
                self.loop.call_soon_threadsafe(self.loop.stop)
                self.app.after(0, self.app._hide_progress_overlay)
                if self.on_disconnected:
                    self.app.after(0, self.on_disconnected)
            self.run_in_background(run)
        elif self.on_disconnected:
            self.app.after(0, self.on_disconnected)

    def get_contacts(self, callback):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            def run():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.service.get_contacts(), self.loop
                    )
                    callback(future.result(timeout=30))
                except Exception:
                    callback([])
            self.run_in_background(run)
        else:
            callback([])

    def get_user_status(self, user_id, callback):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            def run():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.service.get_user_status(user_id), self.loop
                    )
                    callback(future.result(timeout=15))
                except Exception:
                    callback("offline")
            self.run_in_background(run)
        else:
            callback("offline")

    def get_dialogs(self, callback):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            def run():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.service.get_dialogs(), self.loop
                    )
                    callback(future.result(timeout=30))
                except Exception:
                    callback([])
            self.run_in_background(run)
        else:
            callback([])

    def get_user_dialogs(self, callback):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            def run():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.service.get_user_dialogs(), self.loop
                    )
                    callback(future.result(timeout=30))
                except Exception:
                    callback([])
            self.run_in_background(run)
        else:
            callback([])

    def get_messages(self, chat_id, callback):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            def run():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.service.get_messages(chat_id), self.loop
                    )
                    callback(future.result(timeout=30))
                except Exception:
                    callback([{"error": "Message load timed out. The chat may have large media files."}])
            self.run_in_background(run)
        else:
            callback([])

    def send_message(self, chat_id, text):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.service.send_message(chat_id, text), self.loop
            )

    def make_call(self, user_id, video=False):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.service.make_call(user_id, video), self.loop
            )

    def answer_call(self):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.service.answer_call(), self.loop
            )

    def reject_call(self):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.service.reject_call(), self.loop
            )

    def end_call(self):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.service.end_call(), self.loop
            )

    def mark_as_read(self, chat_id):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.service.mark_as_read(chat_id), self.loop
            )

    def send_file(self, chat_id, file_path):
        if self.loop and self.loop.is_running() and self.service.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.service.send_file(chat_id, file_path), self.loop
            )


if __name__ == "__main__":
    app = TelegramApp()
    app.mainloop()
