# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from src.services.signal_service import SignalService
from src.services.supabase_service import SupabaseService
from src.models.schemas import StaffAssignment, User
import threading
import asyncio
import sys
import os
import json
import time
import mimetypes
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)
import qrcode
from PIL import Image, ImageTk
from src.config.settings import SESSION_DIR, APP_DIR

# Signal colors — updated palette
BG = "#FFFFFF"
SIDEBAR_BG = "#F3F4F6"
HEADER_BG = "#FFFFFF"
SENT_BUBBLE = "#2563EB"
RECEIVED_BUBBLE = "#E5E7EB"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#6B7280"
SEARCH_BG = "#E5E7EB"
INPUT_BG = "#F3F4F6"
ACCENT = "#2563EB"
HOVER = "#E5E5E5"
BADGE_BG = "#1D4ED8"
ACTIVE_BG = "#E5E5E5"
CALLS_ENABLED = False  # set True when signal-call-tunnel binary becomes available

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")


class SignalApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Signal Staff Control")
        self.geometry("1200x700")
        self.minsize(900, 600)

        self._logo_pil = None
        self._logocache = {}
        try:
            ico_path = os.path.join(str(APP_DIR), "icon.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(default=ico_path)
        except Exception:
            pass
        self.supabase = SupabaseService()
        self.current_user: Optional[User] = None
        self.workers: dict[str, "SignalWorker"] = {}
        self.current_worker: Optional["SignalWorker"] = None
        self.active_chat: Optional[str] = None
        self._active_chat_name: str = ""
        self.messages_cache: dict[str, list] = {}
        self._unread_counts: dict[str, int] = {}
        self._chat_widgets: dict[str, dict] = {}
        self._contacts_map: dict[str, dict] = {}
        self._call_state: Optional[str] = None
        self._current_call_id: Optional[str] = None
        self._call_contact: Optional[str] = None
        self._call_display_name: str = ""
        self._call_popup: Optional[ctk.CTkToplevel] = None
        self._last_bubble_sender: str = ""
        self.current_user = self.supabase.restore_session()
        if self.current_user:
            self._setup_main_ui()
            self._load_assignments()
        else:
            self._setup_login_ui()

    # ===================== Sound helpers (Windows) =====================

    _ringtone_path: Optional[str] = None

    @staticmethod
    def _generate_ringtone_wav() -> str:
        import wave, struct, math, tempfile
        sample_rate, duration = 22050, 2.0
        n = int(sample_rate * duration)
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        with wave.open(f.name, 'w') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
            for i in range(n):
                t = i / sample_rate
                cycle = t % 2.0
                if cycle < 0.4:
                    val = int(0.4 * 32767 * math.sin(2 * math.pi * 440 * t))
                elif cycle < 0.8:
                    val = int(0.35 * 32767 * math.sin(2 * math.pi * 480 * t))
                else:
                    val = 0
                wf.writeframes(struct.pack('<h', val))
        return f.name

    def _play_notification(self):
        if sys.platform != "win32":
            return
        import winsound
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    def _play_ringtone_loop(self):
        if sys.platform != "win32":
            return
        import winsound
        if not SignalApp._ringtone_path:
            SignalApp._ringtone_path = self._generate_ringtone_wav()
        try:
            winsound.PlaySound(SignalApp._ringtone_path,
                               winsound.SND_ASYNC | winsound.SND_LOOP | winsound.SND_NODEFAULT)
        except Exception:
            pass

    def _stop_sound(self):
        if sys.platform != "win32":
            return
        import winsound
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def _messages_path(self) -> str:
        if self.current_worker and self.current_worker.service.number:
            return str(SESSION_DIR / f"messages_{self.current_worker.service.number}.json")
        return ""

    def _save_messages(self):
        logger.info(f"_save_messages: {sum(len(v) for v in self.messages_cache.values())} msgs across {len(self.messages_cache)} chats")
        path = self._messages_path()
        if path:
            with open(path, "w") as f:
                json.dump(self.messages_cache, f, indent=2)

    def _load_messages(self):
        logger.info("_load_messages")
        path = self._messages_path()
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    self.messages_cache = json.load(f)
                logger.info(f"Loaded {sum(len(v) for v in self.messages_cache.values())} cached messages across {len(self.messages_cache)} chats")
            except Exception as e:
                logger.info(f"Failed to load messages: {e}")
        else:
            logger.info("no messages file found")

    def _get_logo_pil(self, size=80):
        if self._logo_pil is None:
            try:
                logo_path = os.path.join(str(APP_DIR), "logo.webp")
                if os.path.exists(logo_path):
                    self._logo_pil = Image.open(logo_path)
            except Exception:
                pass
        if self._logo_pil is None:
            return None
        key = (size, size)
        if key not in self._logocache:
            copy = self._logo_pil.copy()
            copy.thumbnail((size, size))
            self._logocache[key] = copy
        return self._logocache[key]

    def _get_logo_ctk(self, size=80):
        pil = self._get_logo_pil(size)
        if pil:
            return ctk.CTkImage(pil, size=(pil.width, pil.height))
        return None

    # ===================== LOGIN =====================

    def _setup_login_ui(self):
        self.login_frame = tk.Frame(self, bg=BG)
        self.login_frame.pack(fill="both", expand=True)

        # Logo
        logo_pil = self._get_logo_pil(100)
        if logo_pil:
            from PIL import ImageTk
            logo_tk = ImageTk.PhotoImage(logo_pil)
            logo_label = tk.Label(self.login_frame, image=logo_tk, bg=BG)
            logo_label.image = logo_tk
            logo_label.pack(pady=(60, 10))
        else:
            tk.Label(self.login_frame, text="", font=("Segoe UI", 24, "bold"),
                      fg=ACCENT, bg=BG).pack(pady=(60, 5))

        tk.Label(self.login_frame, text="Signal Staff Control", font=("Segoe UI", 24, "bold"),
                  fg=ACCENT, bg=BG).pack(pady=(0, 5))
        tk.Label(self.login_frame, text="Sign in to your account", font=("Segoe UI", 13),
                  fg=TEXT_SECONDARY, bg=BG).pack(pady=(0, 30))

        entry_frame = tk.Frame(self.login_frame, bg=BG)
        entry_frame.pack()

        tk.Label(entry_frame, text="Email", font=("Segoe UI", 12), fg=TEXT_PRIMARY,
                  bg=BG, anchor="w").pack(fill="x")
        self.email_entry = tk.Entry(entry_frame, font=("Segoe UI", 13), relief="flat",
                                     bg="#f0f0f0", fg=TEXT_PRIMARY, width=35)
        self.email_entry.pack(ipady=8, pady=(5, 15))

        tk.Label(entry_frame, text="Password", font=("Segoe UI", 12), fg=TEXT_PRIMARY,
                  bg=BG, anchor="w").pack(fill="x")
        self.password_entry = tk.Entry(entry_frame, font=("Segoe UI", 13), relief="flat",
                                        bg="#f0f0f0", fg=TEXT_PRIMARY, width=35, show="*")
        self.password_entry.pack(ipady=8, pady=(5, 25))
        self.password_entry.bind("<Return>", lambda e: self._handle_login())

        self.login_btn = tk.Button(entry_frame, text="Sign In", command=self._handle_login,
                                    bg=ACCENT, fg="white", relief="flat",
                                    font=("Segoe UI", 14, "bold"), cursor="hand2",
                                    borderwidth=0, padx=20, pady=8)
        self.login_btn.pack(pady=(0, 60))
        self.login_btn.bind("<Enter>", lambda e: self.login_btn.configure(bg="#1851b4"))
        self.login_btn.bind("<Leave>", lambda e: self.login_btn.configure(bg=ACCENT))

    def _check_internet(self) -> bool:
        try:
            import socket
            socket.create_connection(("1.1.1.1", 53), timeout=3).close()
            return True
        except (OSError, socket.error):
            messagebox.showerror("No Internet",
                "No internet connection detected.\n\nPlease connect to the internet and try again.")
            return False

    def _handle_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        logger.info(f"_handle_login: email='{email}', pw_len={len(password)}")
        if not email or not password:
            logger.info("_handle_login: missing credentials")
            messagebox.showerror("Error", "Email and password are required")
            return
        if not self._check_internet():
            logger.info("_handle_login: no internet")
            return
        self.login_btn.configure(state="disabled", text="Signing in...")
        self.update_idletasks()
        self.current_user = self.supabase.sign_in(email, password)
        logger.info(f"_handle_login: user={'found' if self.current_user else 'None'}")
        if self.current_user:
            self.supabase.save_session()
            self.login_frame.destroy()
            self._setup_main_ui()
            self._load_assignments()
        else:
            self.login_btn.configure(state="normal", text="Sign In")
            messagebox.showerror("Error", "Invalid email or password")

    # ===================== SETUP MAIN UI =====================

    def _setup_main_ui(self):
        self.configure(fg_color=BG)

        # Thin top status bar
        self.top_bar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, height=40, corner_radius=0)
        self.top_bar.pack(fill="x", side="top")
        self.top_bar.pack_propagate(False)

        self.status_dot = ctk.CTkLabel(self.top_bar, text="", width=8, height=8,
                                        fg_color="#ccc", corner_radius=4)
        self.status_dot.pack(side="left", padx=(15, 5), pady=12)
        self.status_label = ctk.CTkLabel(self.top_bar, text="Disconnected",
                                          font=("Inter", 11), text_color=TEXT_SECONDARY)
        self.status_label.pack(side="left")

        # Setup buttons container
        self.setup_buttons_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.setup_buttons_frame.pack(side="right", padx=10)

        self.link_btn = ctk.CTkButton(self.setup_buttons_frame, text="Link", command=self._show_link_dialog,
                                       fg_color="transparent", text_color=ACCENT, hover_color=HOVER,
                                       font=("Inter", 11), border_width=0, width=50, height=28)
        self.link_btn.pack(side="left", padx=2)

        self.logout_btn = ctk.CTkButton(self.setup_buttons_frame, text="Logout",
                                         command=self._logout,
                                         fg_color="transparent", text_color="#E53935", hover_color=HOVER,
                                         font=("Inter", 11), border_width=0, width=55, height=28)
        self.logout_btn.pack(side="left", padx=2)

        self.register_btn = ctk.CTkButton(self.setup_buttons_frame, text="Register",
                                           command=self._show_register_dialog,
                                           fg_color="transparent", text_color=ACCENT, hover_color=HOVER,
                                           font=("Inter", 11), border_width=0, width=60, height=28)

        self.use_number_btn = ctk.CTkButton(self.setup_buttons_frame, text="Use Number",
                                             command=self._show_use_number_dialog,
                                             fg_color="transparent", text_color=ACCENT, hover_color=HOVER,
                                             font=("Inter", 11), border_width=0, width=70, height=28)
        self.use_number_btn.pack(side="left", padx=2)

        # Main content area
        self.main_content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main_content.pack(fill="both", expand=True)

        # ============ LEFT SIDEBAR ============
        self.sidebar = ctk.CTkFrame(self.main_content, fg_color=SIDEBAR_BG, width=400, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Sidebar top section: profile avatar + search
        self.sidebar_top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_top.pack(fill="x", padx=12, pady=(12, 8))

        # Profile avatar (44px) — show logo or user initial
        self.profile_avatar = ctk.CTkFrame(self.sidebar_top, width=44, height=44,
                                            corner_radius=22, fg_color=ACCENT)
        self.profile_avatar.pack(side="left")
        self.profile_avatar.pack_propagate(False)
        logo_ctk = self._get_logo_ctk(40)
        if logo_ctk:
            ctk.CTkLabel(self.profile_avatar, image=logo_ctk, text="").pack(expand=True)
        else:
            user_initial = self.current_user.email[0].upper() if self.current_user and self.current_user.email else "U"
            ctk.CTkLabel(self.profile_avatar, text=user_initial, font=("Inter", 18, "bold"),
                          text_color="#FFFFFF").pack(expand=True)

        # Search bar (pill-shaped)
        self.search_entry = ctk.CTkEntry(self.sidebar_top, placeholder_text="Search",
                                          height=36, fg_color=SEARCH_BG, border_width=0,
                                          corner_radius=18, placeholder_text_color=TEXT_SECONDARY)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_chats())

        # Chat list (scrollable)
        self.chat_list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent",
                                                        corner_radius=0,
                                                        scrollbar_button_color="#ccc",
                                                        scrollbar_button_hover_color="#aaa")
        self.chat_list_frame.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        self.no_chats_label = ctk.CTkLabel(self.chat_list_frame, text="No conversations yet",
                                            font=("Inter", 13), text_color=TEXT_SECONDARY)
        self.no_chats_label.pack(pady=40)

        # ============ RIGHT CHAT PANEL ============
        self.chat_panel = ctk.CTkFrame(self.main_content, fg_color=BG, corner_radius=0)
        self.chat_panel.pack(side="right", fill="both", expand=True)

        # Chat header
        self.chat_header = ctk.CTkFrame(self.chat_panel, fg_color=HEADER_BG, height=60, corner_radius=0)
        self.chat_header.pack(fill="x")
        self.chat_header.pack_propagate(False)

        # Left spacer
        ctk.CTkLabel(self.chat_header, text="", width=20).pack(side="left")

        # Group/contact avatar in header
        self.chat_header_avatar = ctk.CTkFrame(self.chat_header, width=36, height=36,
                                                corner_radius=18, fg_color="transparent")
        self.chat_header_avatar.pack(side="left")
        self.chat_header_avatar.pack_propagate(False)

        # Centered name + typing indicator
        self.chat_header_label = ctk.CTkLabel(self.chat_header, text="Select a conversation",
                                               font=("Inter", 16, "bold"), text_color=TEXT_PRIMARY)
        self.chat_header_label.pack(side="left", expand=True, padx=(0, 0))
        self.typing_indicator = ctk.CTkLabel(self.chat_header, text="",
                                              font=("Inter", 11), text_color=TEXT_SECONDARY)
        self.typing_indicator.pack(side="left", padx=(4, 0))
        self.typing_indicator.pack_forget()
        self._typing_timer = None  # for hiding typing indicator after timeout

        # Search + menu icons on right
        self.chat_search_btn = ctk.CTkButton(self.chat_header, text="🔍", width=36, height=36,
                                               font=("Inter", 14), corner_radius=18,
                                               fg_color="transparent", text_color=TEXT_SECONDARY,
                                               hover_color=HOVER, command=self._show_message_search)
        self.chat_search_btn.pack(side="right", padx=(0, 2), pady=12)

        self.call_btn = ctk.CTkButton(self.chat_header, text="📞", width=36, height=36,
                                       font=("Inter", 16), corner_radius=18,
                                       fg_color="transparent", text_color=TEXT_SECONDARY,
                                       hover_color=HOVER, command=self._start_call)
        self.call_btn.pack(side="right", padx=(0, 12), pady=12)
        if not CALLS_ENABLED:
            self.call_btn.configure(state="disabled")
            self.call_btn.bind("<Enter>", lambda e: self._show_toast("Voice calls require signal-call-tunnel binary", ""))

        # Separator line
        separator = ctk.CTkFrame(self.chat_header, height=1, fg_color="#E5E7EB", corner_radius=0)
        separator.pack(fill="x", side="bottom")

        # Messages container
        self.messages_container = ctk.CTkScrollableFrame(self.chat_panel, fg_color=BG, corner_radius=0)
        self.messages_container.pack(fill="both", expand=True)

        self.no_chat_selected = ctk.CTkFrame(self.messages_container, fg_color="transparent")
        self.no_chat_selected.pack(expand=True)
        ctk.CTkLabel(self.no_chat_selected, text="Select a conversation\nto start messaging",
                      font=("Inter", 16), text_color=TEXT_SECONDARY, justify="center").pack()

        # Loading bar (hidden by default) — placed at top of messages area
        self._loading_bar = ctk.CTkProgressBar(self.messages_container, height=4,
                                                corner_radius=0, mode="indeterminate")
        self._loading_label = ctk.CTkLabel(self.messages_container, text="",
                                            font=("Inter", 11), text_color=TEXT_SECONDARY)
        self._loading_bar.place_forget()
        self._loading_label.place_forget()

        # Bottom input area
        self.input_frame = ctk.CTkFrame(self.chat_panel, fg_color=BG, corner_radius=0)
        self.input_frame.pack(fill="x")
        self.input_frame.pack_forget()

        input_container = ctk.CTkFrame(self.input_frame, fg_color=INPUT_BG, corner_radius=24)
        input_container.pack(fill="x", padx=16, pady=(8, 16))

        self.attach_btn = ctk.CTkButton(input_container, text="📎", command=self._attach_file,
                                         width=36, height=32, corner_radius=16,
                                         fg_color="transparent", text_color=TEXT_SECONDARY,
                                         hover_color=HOVER, font=("Inter", 14))
        self.attach_btn.pack(side="left", padx=(6, 2))

        self.message_entry = ctk.CTkEntry(input_container, placeholder_text="Type a message",
                                           height=40, fg_color="transparent", border_width=0,
                                           corner_radius=20)
        self.message_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=2)
        self.message_entry.bind("<Return>", lambda e: self._send_message())
        self.message_entry.bind("<KeyPress>", lambda e: self._on_user_typing())
        self._typing_debounce = None  # for debounced typing stop
        self._last_typing_sent = 0.0  # rate-limit for typing indicators
        self._pending_read_receipts = set()  # timestamps currently being sent

        self.send_btn = ctk.CTkButton(input_container, text="Send", command=self._send_message,
                                       fg_color=ACCENT, hover_color="#1D4ED8",
                                       width=60, height=32, corner_radius=16,
                                       font=("Inter", 12, "bold"), border_width=0)
        self.send_btn.pack(side="right", padx=(0, 6))

        # Dialogs (hidden by default)
        self._dialog_frame = None

    # ===================== CHAT LIST =====================

    AVATAR_COLORS = ["#2563EB", "#7C3AED", "#EC4899", "#F59E0B", "#10B981", "#EF4444", "#6366F1", "#14B8A6"]

    def _get_avatar_color(self, name: str) -> str:
        idx = abs(hash(name)) % len(self.AVATAR_COLORS)
        return self.AVATAR_COLORS[idx]

    def _update_chat_list(self):
        logger.debug("_update_chat_list called")
        for w in self.chat_list_frame.winfo_children():
            w.destroy()
        self._chat_widgets.clear()
        if not self.current_worker:
            logger.debug("no current_worker")
            return

        contacts = getattr(self.current_worker, '_contacts_cache', None)
        if not contacts:
            logger.debug("no contacts, showing placeholder")
            self.no_chats_label = ctk.CTkLabel(self.chat_list_frame, text="No conversations yet",
                                                font=("Inter", 13), text_color=TEXT_SECONDARY)
            self.no_chats_label.pack(pady=40)
            return

        self._contacts_map.clear()
        for c in contacts:
            self._contacts_map[c.get("number")] = c

        for contact in contacts:
            number = contact.get("number", "")
            name = contact.get("name", "") or "Unknown"
            masked = contact.get("masked", False)
            messages = self.messages_cache.get(number, [])
            last_msg = messages[-1] if messages else None
            preview = last_msg.get("text", "")[:50] if last_msg else ""
            time_str = last_msg.get("time", "") if last_msg else ""
            unread = self._unread_counts.get(number, 0)
            self._add_chat_item(number, name, masked, preview, time_str, unread)

    def _add_chat_item(self, number: str, name: str, masked: bool = False,
                       preview: str = "", time_str: str = "", unread: int = 0):
        search_text = (name + " " + number).lower()
        is_active = number == self.active_chat

        frame = ctk.CTkFrame(self.chat_list_frame, fg_color=ACTIVE_BG if is_active else "transparent",
                              corner_radius=12)
        frame.pack(fill="x", padx=8, pady=2)
        frame._search_text = search_text
        frame._number = number
        frame.bind("<Button-1>", lambda e, n=number, nm=name: self._open_chat(n, nm))
        frame.bind("<Enter>", lambda e, f=frame: f.configure(fg_color=ACTIVE_BG if f._number == self.active_chat else HOVER))
        frame.bind("<Leave>", lambda e, f=frame: f.configure(fg_color=ACTIVE_BG if f._number == self.active_chat else "transparent"))

        # Inner row
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)
        inner._number = number
        inner.bind("<Button-1>", lambda e, n=number, nm=name: self._open_chat(n, nm))

        # Avatar container
        avatar_container = ctk.CTkFrame(inner, width=44, height=44, fg_color="transparent")
        avatar_container.pack(side="left")
        avatar_container.pack_propagate(False)
        avatar_container._number = number
        avatar_container.bind("<Button-1>", lambda e, n=number, nm=name: self._open_chat(n, nm))

        # Avatar circle
        avatar_color = self._get_avatar_color(name)
        avatar = ctk.CTkFrame(avatar_container, width=44, height=44, corner_radius=22,
                               fg_color=avatar_color)
        avatar.pack()
        avatar.pack_propagate(False)
        initial = name[0].upper() if name else "#"
        initial_lbl = ctk.CTkLabel(avatar, text=initial, font=("Inter", 16, "bold"),
                      text_color="#FFFFFF")
        initial_lbl.pack(expand=True)

        # Unread badge
        badge = ctk.CTkLabel(avatar_container, text="", width=20, height=20,
                              corner_radius=10, fg_color=BADGE_BG, text_color="#FFFFFF",
                              font=("Inter", 10, "bold"))
        if unread > 0:
            badge.configure(text=str(unread))
            badge.place(x=28, y=-4)

        # Text area
        text_area = ctk.CTkFrame(inner, fg_color="transparent")
        text_area.pack(side="left", fill="x", expand=True, padx=(12, 0))
        text_area._number = number
        text_area.bind("<Button-1>", lambda e, n=number, nm=name: self._open_chat(n, nm))

        # Name row
        name_row = ctk.CTkFrame(text_area, fg_color="transparent")
        name_row.pack(fill="x")
        name_row._number = number
        name_row.bind("<Button-1>", lambda e, n=number, nm=name: self._open_chat(n, nm))

        name_lbl = ctk.CTkLabel(name_row, text=name, font=("Inter", 14, "bold"),
                                text_color=TEXT_PRIMARY, anchor="w")
        name_lbl.pack(side="left")
        time_lbl = ctk.CTkLabel(name_row, text=time_str, font=("Inter", 11),
                                 text_color=TEXT_SECONDARY, anchor="e")
        time_lbl.pack(side="right")

        # Preview row
        preview_row = ctk.CTkFrame(text_area, fg_color="transparent")
        preview_row.pack(fill="x")
        preview_row._number = number
        preview_row.bind("<Button-1>", lambda e, n=number, nm=name: self._open_chat(n, nm))

        preview_text = ("🔒 " if masked else "") + preview
        preview_lbl = ctk.CTkLabel(preview_row, text=preview_text, font=("Inter", 12),
                                    text_color=TEXT_SECONDARY, anchor="w")
        preview_lbl.pack(side="left")

        # Store widget references for real-time updates
        self._chat_widgets[number] = {
            "frame": frame, "name": name, "masked": masked,
            "name_lbl": name_lbl, "time_lbl": time_lbl,
            "preview_lbl": preview_lbl, "badge": badge,
            "avatar_container": avatar_container,
            "avatar": avatar, "initial_lbl": initial_lbl
        }

    def _filter_chats(self):
        search = self.search_entry.get().strip().lower()
        for child in self.chat_list_frame.winfo_children():
            text = getattr(child, "_search_text", "")
            if search:
                if search in text:
                    child.pack(fill="x", padx=8, pady=2)
                else:
                    child.pack_forget()
            else:
                child.pack(fill="x", padx=8, pady=2)

    def _refresh_sidebar(self):
        """Update sidebar items with latest messages, unreads, and add new contacts."""
        if not self.current_worker:
            return
        contacts = getattr(self.current_worker, '_contacts_cache', None)
        if not contacts:
            return
        logger.info(f"_refresh_sidebar: {len(contacts)} contacts, {len(self._chat_widgets)} widgets, {len(self._unread_counts)} unreads")

        # Update existing widgets and track which numbers still exist
        seen = set()
        for contact in contacts:
            number = contact.get("number", "")
            name = contact.get("name", "") or "Unknown"
            seen.add(number)
            messages = self.messages_cache.get(number, [])
            last_msg = messages[-1] if messages else None
            preview = last_msg.get("text", "")[:50] if last_msg else ""
            time_str = last_msg.get("time", "") if last_msg else ""
            unread = self._unread_counts.get(number, 0)

            if number in self._chat_widgets:
                w = self._chat_widgets[number]
                if w["name"] != name:
                    w["name"] = name
                    w["name_lbl"].configure(text=name)
                w["time_lbl"].configure(text=time_str)
                masked_text = ("🔒 " if w["masked"] else "") + preview
                w["preview_lbl"].configure(text=masked_text)
                if unread > 0:
                    w["badge"].configure(text=str(unread))
                    try:
                        w["badge"].place(x=28, y=-4)
                    except Exception:
                        pass
                else:
                    try:
                        w["badge"].place_forget()
                    except Exception:
                        pass
            else:
                # New contact not yet in sidebar
                self._add_chat_item(number, name, contact.get("masked", False), preview, time_str, unread)

        # Remove contacts from cache that are no longer in contact list
        stale = [n for n in self._chat_widgets if n not in seen]
        for n in stale:
            try:
                self._chat_widgets[n]["frame"].destroy()
            except Exception:
                pass
            del self._chat_widgets[n]

    def _start_sidebar_refresh(self):
        """Start periodic sidebar refresh (every 2 seconds)."""
        self._refresh_sidebar()
        self.after(2000, self._start_sidebar_refresh)

    # ===================== OPEN CHAT =====================

    def _open_chat(self, number: str, name: str):
        # Always use latest name from contacts map (Supabase names), never phone number
        mapped = self._contacts_map.get(number, {})
        name = mapped.get("name", "") or "Unknown"
        if name == "Unknown" and number not in self._contacts_map:
            self._resolve_client_name(number)
        logger.info(f"_open_chat: number='{number}', name='{name}'")
        self.active_chat = number
        self._active_chat_name = name
        self.chat_header_label.configure(text=name)

        # Update header avatar
        avatar_color = self._get_avatar_color(name)
        for w in self.chat_header_avatar.winfo_children():
            w.destroy()
        ha = ctk.CTkFrame(self.chat_header_avatar, width=36, height=36, corner_radius=18,
                           fg_color=avatar_color)
        ha.pack()
        ha.pack_propagate(False)
        ctk.CTkLabel(ha, text=name[0].upper() if name else "#", font=("Inter", 14, "bold"),
                      text_color="#FFFFFF").pack(expand=True)

        # Update chat list highlighting
        for child in self.chat_list_frame.winfo_children():
            if hasattr(child, '_number'):
                is_active = child._number == number
                child.configure(fg_color=ACTIVE_BG if is_active else "transparent")

        # Reset unread count
        self._unread_counts[number] = 0

        self.no_chat_selected.pack_forget()
        self.input_frame.pack(fill="x")

        self._last_bubble_sender = ""

        for w in self.messages_container.winfo_children():
            if w != self.no_chat_selected:
                w.destroy()
        self.no_chat_selected.pack_forget()

        cache_key = number
        messages = self.messages_cache.get(cache_key, [])
        unread_ts = []
        for msg in messages:
            downloaded = msg.get("downloaded", [])
            reactions = msg.get("reactions", [])
            self._add_message_bubble(msg.get("text", ""), msg.get("is_sent", True),
                                     msg.get("time", ""), msg.get("status", ""), downloaded,
                                     msg.get("sender", ""), reactions)
            if msg.get("is_sent") and msg.get("status") in ("delivered", "read", "sent"):
                if not msg.get("read_receipt_sent"):
                    unread_ts.append(msg.get("server_timestamp"))

        # Send read receipts for delivered messages in this chat
        if unread_ts and self.current_worker and self.current_worker.service.is_connected:
            import threading as _t
            _t.Thread(target=self._send_read_receipts, args=(number, unread_ts), daemon=True).start()

        if self.current_worker and self.current_worker.service.is_connected:
            pass  # polling loop handles incoming messages

        # Scroll to bottom
        self.messages_container.update_idletasks()
        try:
            self.messages_container._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _format_time(self, ts: str) -> str:
        try:
            if ts and ts.isdigit():
                ts_int = int(ts) // 1000 if len(ts) > 11 else int(ts)
                from datetime import datetime
                dt = datetime.fromtimestamp(ts_int)
                now = datetime.now()
                if dt.date() == now.date():
                    return dt.strftime("%I:%M %p").lstrip("0")
                elif dt.year == now.year:
                    return dt.strftime("%b %d")
                return dt.strftime("%b %d, %Y")
        except (ValueError, OSError):
            pass
        return ts or ""

    def _download_attachments(self, attachments: list, contact: str, timestamp: str):
        logger.info(f"_download_attachments: {len(attachments)} attachments, contact='{contact}', ts='{timestamp}'")
        import asyncio, os, tempfile
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for att in attachments:
            att_id = str(att.get("id", "")).strip()
            logger.info(f"_download_attachments: att_id='{att_id}', content_type='{att.get('contentType','')}'")
            if not att_id or att_id in ("0", "None") or not self.current_worker:
                continue
            content_type = att.get("contentType", "")
            data = loop.run_until_complete(
                self.current_worker.service.download_attachment(att_id, contact)
            )
            if data:
                ext = os.path.splitext(att_id)[1] or ".bin"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                tmp.write(data)
                tmp.close()
                path = tmp.name
                # Update cache entry
                for msgs in self.messages_cache.values():
                    for m in msgs:
                        if m.get("server_timestamp") == timestamp and m.get("sender") == contact:
                            if "downloaded" not in m:
                                m["downloaded"] = []
                            m["downloaded"].append({"path": path, "contentType": content_type})
                            break
                self._save_messages()
                # Update bubble if chat is open
                if self.active_chat == contact:
                    self.after(0, self._redisplay_messages)
        loop.close()

    def _add_message_bubble(self, text: str, is_sent: bool, time: str = "", status: str = "",
                            attachments: list = None, sender: str = "", reactions: list = None):
        bubble_frame = ctk.CTkFrame(self.messages_container, fg_color="transparent")
        bubble_frame.pack(fill="x", padx=20, pady=(2, 2))

        anchor = "e" if is_sent else "w"
        card_bg = SENT_BUBBLE if is_sent else RECEIVED_BUBBLE
        text_color_body = "#FFFFFF" if is_sent else TEXT_PRIMARY
        text_color_secondary = "#B0B0B0" if is_sent else TEXT_SECONDARY

        # Sender name — only show if different from previous message
        if not is_sent and sender and sender != self._last_bubble_sender:
            # Look up friendly name
            mapped = self._contacts_map.get(sender, {})
            display_sender = mapped.get("name", "") or "Unknown"
            ctk.CTkLabel(bubble_frame, text=display_sender, font=("Inter", 11, "bold"),
                          text_color=TEXT_SECONDARY, anchor="w").pack(fill="x", padx=(12, 0), pady=(0, 2))
        if not is_sent:
            self._last_bubble_sender = sender

        # Helper: pack an attachment card with proper styling
        def pack_card(frame, side_anchor=anchor):
            frame.pack(fill="x", padx=0, pady=(0, 4))
            frame.configure(corner_radius=16)

        # Helper: detect content type from path as fallback
        def _detect_ct(p):
            _, ext = os.path.splitext(p)
            ext = ext.lower()
            if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
                return "image/" + ext.lstrip(".")
            if ext in (".aac", ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".wma"):
                return "audio/" + ext.lstrip(".")
            return None

        # Handle attachments
        if attachments:
            for att in attachments:
                ct = att.get("contentType", "") or _detect_ct(att.get("path", "")) or ""
                path = att.get("path", "")
                if ct.startswith("image/") and path and os.path.exists(path):
                    try:
                        img = Image.open(path)
                        display_w = min(img.width, 320)
                        display_h = int(img.height * (display_w / img.width))
                        img.thumbnail((display_w, display_h))
                        ctk_img = ctk.CTkImage(img, size=(display_w, display_h))
                        img_frame = ctk.CTkFrame(bubble_frame, fg_color=card_bg, corner_radius=12)
                        img_frame.pack(anchor=anchor, pady=(0, 4))
                        img_lbl = ctk.CTkLabel(img_frame, image=ctk_img, text="")
                        img_lbl.pack()
                        img_lbl.bind("<Button-1>", lambda e, p=path: os.startfile(p))
                        if time:
                            overlay = ctk.CTkFrame(img_frame, fg_color="#00000099")
                            ctk.CTkLabel(overlay, text=time, font=("Inter", 10),
                                          text_color="#FFFFFF").pack(padx=8, pady=2)
                            overlay.place(relx=0.0, rely=1.0, anchor="sw", x=8, y=-8)
                    except Exception as e:
                        logger.info(f"Image display error: {e}")
                elif ct.startswith("audio/") and path and os.path.exists(path):
                    audio_card = ctk.CTkFrame(bubble_frame, fg_color=card_bg, corner_radius=16)
                    audio_card.pack(anchor=anchor, pady=(0, 4))
                    play_btn = ctk.CTkButton(audio_card, text="▶", width=40, height=40,
                                              font=("Inter", 16), corner_radius=20,
                                              fg_color="#4CAF50", hover_color="#388E3C", text_color="#fff")
                    play_btn.pack(side="left", padx=8, pady=8)
                    waveform_frame = ctk.CTkFrame(audio_card, fg_color="transparent")
                    waveform_frame.pack(side="left", fill="x", expand=True, padx=(8, 12), pady=8)
                    for bar_h in [10, 18, 6, 26, 14, 22, 8, 30, 16, 12, 24, 10, 20, 6, 28, 14]:
                        bar = ctk.CTkFrame(waveform_frame, width=3, height=bar_h,
                                           fg_color="#4CAF50", corner_radius=2)
                        bar.pack(side="left", padx=1)
                    play_btn.bind("<Button-1>", lambda e, p=path: os.startfile(p))
                elif path and os.path.exists(path):
                    _, ext = os.path.splitext(path)
                    ext = ext.lower()
                    file_icon = "📄"
                    if ext in (".pdf",):
                        file_icon = "📕"
                    elif ext in (".doc", ".docx", ".docm"):
                        file_icon = "📘"
                    elif ext in (".xls", ".xlsx", ".xlsm", ".csv"):
                        file_icon = "📗"
                    elif ext in (".zip", ".rar", ".7z", ".tar", ".gz"):
                        file_icon = "📦"
                    elif ext in (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma"):
                        file_icon = "🎵"
                    elif ext in (".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"):
                        file_icon = "🎬"
                    elif ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
                        file_icon = "🖼"
                    file_card = ctk.CTkFrame(bubble_frame, fg_color=card_bg, corner_radius=12)
                    file_card.pack(anchor=anchor, pady=(0, 4), fill="x")
                    file_card.bind("<Button-1>", lambda e, p=path: os.startfile(p))
                    ctk.CTkLabel(file_card, text=file_icon, font=("Inter", 24)).pack(side="left", padx=12, pady=12)
                    file_info = ctk.CTkFrame(file_card, fg_color="transparent")
                    file_info.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=12)
                    file_name = os.path.basename(path)
                    ctk.CTkLabel(file_info, text=file_name, font=("Inter", 12, "bold"),
                                  text_color=text_color_body, anchor="w").pack(fill="x")
                    try:
                        file_size = os.path.getsize(path)
                        size_str = f"{file_size / 1024:.1f} KB" if file_size > 0 else ""
                        ctk.CTkLabel(file_info, text=size_str, font=("Inter", 10),
                                      text_color=text_color_secondary, anchor="w").pack(fill="x")
                    except Exception:
                        pass

        # Text bubble (or attachment-only timestamp)
        if text:
            bubble = ctk.CTkFrame(bubble_frame, fg_color=SENT_BUBBLE if is_sent else RECEIVED_BUBBLE,
                                   corner_radius=18)
            bubble.pack(anchor=anchor, pady=1)
            # Text content
            msg_label = ctk.CTkLabel(bubble, text=text, font=("Inter", 14),
                                      text_color=text_color_body, wraplength=300, justify="left")
            msg_label.pack(padx=14, pady=(10, 4))
            # Bottom row: timestamp + status
            bottom = ctk.CTkFrame(bubble, fg_color="transparent")
            bottom.pack(fill="x", padx=14, pady=(2, 8))
            if time:
                ctk.CTkLabel(bottom, text=time, font=("Inter", 10),
                              text_color=text_color_secondary).pack(side="left")
            if is_sent:
                if status == "read":
                    check = "✓✓"
                    cc = "#90CAF9"
                elif status == "delivered":
                    check = "✓✓"
                    cc = "#B0B0B0"
                else:
                    check = "✓"
                    cc = "#B0B0B0"
                ctk.CTkLabel(bottom, text=check, font=("Inter", 10),
                              text_color=cc).pack(side="right", padx=(4, 0))
        # Reactions row — show emoji below bubble
        self._add_reactions_row(bubble_frame, anchor, reactions or [])
        if not text:
            # Attachment-only — show timestamp below attachments
            if time:
                ctk.CTkLabel(bubble_frame, text=time, font=("Inter", 10),
                              text_color=text_color_secondary).pack(anchor=anchor, pady=(2, 0))

    def _add_reactions_row(self, parent, anchor, reactions):
        if not reactions:
            return
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor=anchor, pady=(1, 0))
        for r in reactions:
            emoji = r.get("emoji", "")
            if emoji:
                ctk.CTkLabel(row, text=emoji, font=("Inter", 18),
                              text_color=TEXT_PRIMARY).pack(side="left", padx=(1, 1))

    # ===================== LINK DEVICE DIALOG =====================

    def _show_link_dialog(self):
        if self._dialog_frame:
            self._destroy_dialog()
            return
        self._dialog_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=12,
                                           border_width=1, border_color="#e0e0e0",
                                           width=400, height=450)
        self._dialog_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self._dialog_frame, text="Link Device", font=("Inter", 18, "bold"),
                      text_color=TEXT_PRIMARY).pack(pady=(25, 5))
        ctk.CTkLabel(self._dialog_frame, text="Open Signal on your phone and scan this QR code",
                      font=("Inter", 12), text_color=TEXT_SECONDARY).pack(pady=(0, 20))

        self.qr_label = ctk.CTkLabel(self._dialog_frame, text="Generating QR code...",
                                      font=("Inter", 12), text_color=TEXT_SECONDARY)
        self.qr_label.pack(expand=True)

        ctk.CTkButton(self._dialog_frame, text="Close", command=self._destroy_dialog,
                       fg_color="transparent", text_color=TEXT_SECONDARY,
                       hover_color=HOVER, font=("Inter", 12), border_width=0
                       ).pack(pady=(15, 20))

        self._generate_qr()

    def _generate_qr(self):
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            service = SignalService()
            url = loop.run_until_complete(service.link_device())
            if url:
                self.after(0, lambda: self._display_qr(url))
                number = loop.run_until_complete(service.wait_for_linked_number())
                if number:
                    self.after(0, lambda: self._on_linked(number))
                else:
                    self.after(0, lambda: self.qr_label.configure(
                        text="Waiting for scan...\nOpen Signal on your phone\nSettings → Linked Devices → Scan"))
            else:
                self.after(0, lambda: self.qr_label.configure(
                    text="Failed to generate QR code.\nCheck signal-cli is installed."))
        threading.Thread(target=run, daemon=True).start()

    def _display_qr(self, url: str):
        self.qr_label.configure(text="Scan this QR code with Signal:", font=("Inter", 12), text_color=TEXT_SECONDARY)
        qr_img = qrcode.make(url)
        img = qr_img.convert("RGB").resize((220, 220), Image.NEAREST)
        imgtk = ctk.CTkImage(light_image=img, dark_image=img, size=(220, 220))
        self.qr_label.configure(image=imgtk)
        self.qr_label.image = imgtk

    def _on_linked(self, number: str):
        self._destroy_dialog()
        self._add_number(number)
        self.after(100, lambda: messagebox.showinfo("Linked", f"Device linked as {number}!\nConnecting..."))
        self.after(200, lambda: self._connect_account())

    def _destroy_dialog(self):
        if self._dialog_frame:
            self._dialog_frame.destroy()
            self._dialog_frame = None

    # ===================== REGISTER DIALOG =====================

    def _show_register_dialog(self):
        if self._dialog_frame:
            self._destroy_dialog()
            return
        self._dialog_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=12,
                                           border_width=1, border_color="#e0e0e0",
                                           width=420, height=520)
        self._dialog_frame.place(relx=0.5, rely=0.5, anchor="center")

        container = ctk.CTkScrollableFrame(self._dialog_frame, fg_color="transparent", height=500)
        container.pack(fill="both", expand=True, padx=0, pady=0)

        ctk.CTkLabel(container, text="Register Number", font=("Inter", 18, "bold"),
                      text_color=TEXT_PRIMARY).pack(pady=(20, 10))

        ctk.CTkLabel(container, text="Phone Number (with country code)", font=("Inter", 12),
                      text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", padx=30)
        self.reg_phone_entry = ctk.CTkEntry(container, placeholder_text="+1234567890",
                                             height=36, fg_color=SEARCH_BG, border_width=0)
        self.reg_phone_entry.pack(fill="x", padx=30, pady=(5, 8))

        self.reg_voice_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(container, text="Voice call (instead of SMS)",
                         variable=self.reg_voice_var, font=("Inter", 11),
                         text_color=TEXT_SECONDARY, fg_color=ACCENT).pack(padx=30, pady=3)

        # Captcha
        ctk.CTkLabel(container, text="Captcha Token (if required)", font=("Inter", 12),
                      text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", padx=30, pady=(8, 0))
        ctk.CTkLabel(container,
                      text="Get it at:\nsignalcaptchas.org/registration/generate.html\nRight-click 'Open Signal' → copy link",
                      font=("Inter", 10), text_color=TEXT_SECONDARY, justify="left", anchor="w"
                      ).pack(fill="x", padx=30, pady=(2, 4))
        self.reg_captcha_entry = ctk.CTkEntry(container, placeholder_text="signalcaptcha://...",
                                               height=36, fg_color=SEARCH_BG, border_width=0)
        self.reg_captcha_entry.pack(fill="x", padx=30, pady=(3, 8))

        self.reg_send_btn = ctk.CTkButton(container, text="Send Code",
                                           command=self._send_registration_code,
                                           fg_color=ACCENT, hover_color="#1851b4",
                                           height=36, corner_radius=18, font=("Inter", 13, "bold"))
        self.reg_send_btn.pack(fill="x", padx=30, pady=8)

        ctk.CTkLabel(container, text="Verification Code", font=("Inter", 12),
                      text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", padx=30)
        self.reg_code_entry = ctk.CTkEntry(container, placeholder_text="123-456",
                                            height=36, fg_color=SEARCH_BG, border_width=0)
        self.reg_code_entry.pack(fill="x", padx=30, pady=(5, 5))
        self.reg_code_entry.bind("<Return>", lambda e: self._verify_code())

        self.reg_verify_btn = ctk.CTkButton(container, text="Verify",
                                             command=self._verify_code,
                                             fg_color="transparent", text_color=ACCENT,
                                             hover_color=HOVER, height=30,
                                             font=("Inter", 12), border_width=0)
        self.reg_verify_btn.pack(pady=(0, 8))

        ctk.CTkButton(container, text="Close", command=self._destroy_dialog,
                       fg_color="transparent", text_color=TEXT_SECONDARY,
                       hover_color=HOVER, font=("Inter", 11), border_width=0
                       ).pack(pady=(5, 15))

    def _send_registration_code(self):
        phone = self.reg_phone_entry.get().strip()
        if not phone:
            messagebox.showerror("Error", "Enter a phone number")
            return
        if not phone.startswith("+"):
            phone = "+" + phone
            self.reg_phone_entry.delete(0, "end")
            self.reg_phone_entry.insert(0, phone)
        captcha = self.reg_captcha_entry.get().strip() if hasattr(self, "reg_captcha_entry") else ""
        self.reg_send_btn.configure(state="disabled", text="Sending...")

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            service = SignalService(phone)
            use_voice = self.reg_voice_var.get()
            success, err = loop.run_until_complete(service.register_number(phone, use_voice, captcha))
            self.after(0, lambda: self._reg_code_sent(success, err))

        threading.Thread(target=run, daemon=True).start()

    def _reg_code_sent(self, success: bool, err: str = ""):
        self.reg_send_btn.configure(state="normal", text="Send Code")
        if success:
            messagebox.showinfo("Code Sent", "Verification code sent. Check your phone.")
        else:
            messagebox.showerror("Error", err or "Failed to send code")

    def _verify_code(self):
        phone = self.reg_phone_entry.get().strip()
        code = self.reg_code_entry.get().strip()
        if not phone or not code:
            messagebox.showerror("Error", "Enter phone and verification code")
            return
        if not phone.startswith("+"):
            phone = "+" + phone

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            service = SignalService(phone)
            success, err = loop.run_until_complete(service.verify_number(phone, code))
            self.after(0, lambda: self._reg_verified(success, phone, err))

        threading.Thread(target=run, daemon=True).start()

    def _reg_verified(self, success: bool, phone: str, err: str = ""):
        if success:
            self._destroy_dialog()
            messagebox.showinfo("Success", f"Number {phone} registered!")
            self._add_number(phone)
            self._connect_account()
        else:
            messagebox.showerror("Error", err or "Verification failed. Check the code and try again.")

    # ===================== USE NUMBER DIALOG =====================

    def _show_use_number_dialog(self):
        if self._dialog_frame:
            self._destroy_dialog()
            return
        self._dialog_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=12,
                                           border_width=1, border_color="#e0e0e0",
                                           width=360, height=220)
        self._dialog_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self._dialog_frame, text="Enter Your Number", font=("Inter", 16, "bold"),
                      text_color=TEXT_PRIMARY).pack(pady=(25, 10))
        ctk.CTkLabel(self._dialog_frame, text="Phone number with country code",
                      font=("Inter", 11), text_color=TEXT_SECONDARY).pack()

        self.use_number_entry = ctk.CTkEntry(self._dialog_frame, placeholder_text="+1234567890",
                                              height=40, fg_color=SEARCH_BG, border_width=0)
        self.use_number_entry.pack(fill="x", padx=30, pady=(10, 15))
        self.use_number_entry.bind("<Return>", lambda e: self._use_number_submit())

        self.use_number_btn_ok = ctk.CTkButton(self._dialog_frame, text="Connect",
                                                command=self._use_number_submit,
                                                fg_color=ACCENT, hover_color="#1851b4",
                                                height=36, corner_radius=18, font=("Inter", 13, "bold"))
        self.use_number_btn_ok.pack(fill="x", padx=30)
        self.use_number_btn_ok.pack_before = lambda: None

        ctk.CTkButton(self._dialog_frame, text="Cancel", command=self._destroy_dialog,
                       fg_color="transparent", text_color=TEXT_SECONDARY,
                       hover_color=HOVER, font=("Inter", 11), border_width=0
                       ).pack(pady=(8, 15))

    def _use_number_submit(self):
        phone = self.use_number_entry.get().strip()
        if not phone:
            messagebox.showerror("Error", "Enter a phone number")
            return
        if not phone.startswith("+"):
            phone = "+" + phone
        self._destroy_dialog()
        self._add_number(phone)
        self.after(200, self._connect_account)

    def _add_number(self, phone: str):
        if self.current_user:
            assignments = self.supabase.get_staff_assignments(self.current_user.id, "signal")
            if assignments:
                valid_numbers = [a.phone_number for a in assignments if a.is_active]
                phone_clean = phone.replace("+", "").replace("-", "").replace(" ", "")
                matched = any(
                    vn.replace("+", "").replace("-", "").replace(" ", "") == phone_clean or
                    phone_clean.endswith(vn.replace("+", "").replace("-", "").replace(" ", ""))
                    for vn in valid_numbers
                )
                if not matched:
                    messagebox.showerror("Error",
                        f"Phone number {phone} is not assigned to you.\n\n"
                        f"Your assigned numbers: {', '.join(valid_numbers) if valid_numbers else 'None'}\n\n"
                        f"Contact your manager to assign this number.")
                    return
        from src.services.signal_service import SignalService
        SignalService.save_account(phone)
        worker = SignalWorker(phone)
        worker.on_connected = self._on_connected
        worker.on_disconnected = self._on_disconnected
        worker.on_message = self._on_message
        worker.on_receipt = self._on_receipt
        worker.on_typing = self._on_typing
        worker.on_reaction = self._on_reaction
        worker.on_contacts = self._on_contacts
        self.workers[phone] = worker
        self.current_worker = worker
        self.setup_buttons_frame.pack_forget()

    # ===================== CONNECT / DISCONNECT =====================

    def _load_assignments(self):
        if not self.current_user:
            return
        from src.services.signal_service import SignalService
        numbers = SignalService.load_accounts()
        logger.debug(f"_load_assignments: accounts from file: {numbers}")
        if not numbers:
            numbers = self._detect_existing_accounts()
            logger.debug(f"_load_assignments: detected: {numbers}")
        # Validate numbers - remove unregistered ones
        if numbers:
            import json as _json
            from src.services.signal_service import SignalService as SS
            valid = []
            for n in numbers:
                svc = SignalService(n)
                out, _, rc = svc._run(["-o", "json", "listAccounts"], timeout=10)
                is_valid = False
                if rc == 0 and out.strip():
                    try:
                        data = _json.loads(out)
                        entries = data if isinstance(data, list) else [data]
                        is_valid = any(e.get("number") == n for e in entries)
                    except _json.JSONDecodeError:
                        is_valid = n in out  # fallback to text check
                if is_valid:
                    valid.append(n)
                else:
                    logger.debug(f"Removing unregistered number: {n}")
                    SS.remove_account(n)
            numbers = valid
            logger.debug(f"_load_assignments: valid numbers: {numbers}")
            if not numbers:
                numbers = self._detect_existing_accounts()
                logger.debug(f"_load_assignments: re-detected: {numbers}")
        for number in numbers:
            worker = SignalWorker(number)
            worker.on_connected = self._on_connected
            worker.on_disconnected = self._on_disconnected
            worker.on_message = self._on_message
            worker.on_receipt = self._on_receipt
            worker.on_typing = self._on_typing
            worker.on_reaction = self._on_reaction
            worker.on_contacts = self._on_contacts
            self.workers[number] = worker
            self.current_worker = worker
        if numbers:
            logger.info(f"_load_assignments: scheduling auto-connect in 500ms")
            self.after(500, self._connect_account)

    def _detect_existing_accounts(self) -> list[str]:
        import asyncio, json
        from src.services.signal_service import SignalService
        try:
            service = SignalService()
            out, err, rc = service._run(["-o", "json", "listAccounts"], timeout=15)
            logger.debug(f"listAccounts: rc={rc}, out='{out[:300]}', err='{err[:200]}'")
            if out.strip():
                try:
                    data = json.loads(out)
                    if isinstance(data, list):
                        nums = [entry.get("number") for entry in data if entry.get("number", "").startswith("+")]
                    elif isinstance(data, dict):
                        nums = [data.get("number")] if data.get("number", "").startswith("+") else []
                    else:
                        nums = []
                except json.JSONDecodeError:
                    nums = []
                if nums:
                    from src.services.signal_service import SignalService as SS
                    for n in nums:
                        SS.save_account(n)
                    logger.debug(f"Detected accounts: {nums}")
                    return nums
        except Exception as e:
            logger.error(f"Detect accounts error: {e}")
        return []

    def _connect_account(self):
        logger.info(f"_connect_account: worker={'yes' if self.current_worker else 'no'}, connected={self.current_worker.service.is_connected if self.current_worker else 'N/A'}")
        if not self.current_worker:
            messagebox.showerror("Error", "No number configured. Link or register a device first.")
            return
        if self.current_worker.service.is_connected:
            logger.info("_connect_account: already connected")
            return
        if not self._check_internet():
            logger.info("_connect_account: no internet")
            return
        self._show_loading("Connecting to Signal...")
        self.status_label.configure(text="Connecting...")
        self.current_worker.connect()

    def _logout(self):
        self._disconnect_account()
        self.supabase.clear_session()
        self.current_user = None
        self.messages_cache.clear()
        self._chat_widgets.clear()
        self._contacts_map.clear()
        self._unread_counts.clear()
        self.workers.clear()
        self.current_worker = None
        for w in self.winfo_children():
            w.destroy()
        self._setup_login_ui()

    def _disconnect_account(self):
        logger.info("_disconnect_account")
        for worker in self.workers.values():
            worker.disconnect()

    def _on_connected(self):
        logger.info("_on_connected")
        self._hide_loading()
        self._load_messages()
        self.after(0, self._update_chat_list)
        self.after(0, lambda: self.status_dot.configure(fg_color="#00c853"))
        self.after(0, lambda: self.status_label.configure(text="Connected", text_color="#00c853"))
        self.after(0, lambda: self.setup_buttons_frame.pack_forget())
        self.after(2000, self._start_sidebar_refresh)
        # Update assignment status in Supabase
        self._update_assignment_status_online()

    def _update_assignment_status_online(self):
        """Set connection_status to 'connected' in Supabase for all assigned numbers."""
        if not self.current_user or not self.current_worker:
            return
        phone = self.current_worker.service.number
        assignments = self.supabase.get_staff_assignments(self.current_user.id, "signal")
        for a in assignments:
            if a.phone_number.replace("+", "") == phone.replace("+", ""):
                import threading as _t
                _t.Thread(target=self.supabase.update_assignment_status,
                          args=(a.id, "connected", {"version": "signal-staff-app"}), daemon=True).start()
                break

    def _on_disconnected(self):
        logger.info("_on_disconnected")
        self.after(0, lambda: self.status_dot.configure(fg_color="#ccc"))
        self.after(0, lambda: self.status_label.configure(text="Disconnected", text_color=TEXT_SECONDARY))
        self._update_assignment_status_offline()

    def _update_assignment_status_offline(self):
        if not self.current_user or not self.current_worker:
            return
        phone = self.current_worker.service.number
        assignments = self.supabase.get_staff_assignments(self.current_user.id, "signal")
        for a in assignments:
            if a.phone_number.replace("+", "") == phone.replace("+", ""):
                import threading as _t
                _t.Thread(target=self.supabase.update_assignment_status,
                          args=(a.id, "disconnected"), daemon=True).start()
                break

    def _show_loading(self, text="Loading..."):
        self._loading_label.configure(text=text)
        self._loading_bar.place(relx=0, rely=0, relwidth=1)
        self._loading_label.place(relx=0.5, rely=0, anchor="n", y=8)
        self._loading_bar.start()
        self.update_idletasks()

    def _hide_loading(self):
        self._loading_bar.place_forget()
        self._loading_label.place_forget()
        self._loading_bar.stop()

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
            toast.configure(fg_color="#333333")
            x = self.winfo_x() + self.winfo_width() - 340
            y = self.winfo_y() + 60
            toast.geometry(f"320x80+{x}+{y}")
            ctk.CTkLabel(toast, text=title, font=("Inter", 12, "bold"), text_color="#ffffff", anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            ctk.CTkLabel(toast, text=message, font=("Inter", 11), text_color="#cccccc", anchor="w", wraplength=280).pack(fill="x", padx=12, pady=(2, 8))
            toast.after(duration, toast.destroy)
        except Exception:
            pass

    def _on_message(self, msg):
        logger.debug(f"_on_message called with: {msg}")
        text = msg.get("text", "")
        worker_number = self.current_worker.service.number if self.current_worker else ""
        sender = msg.get("sender_id", "")
        raw_ts = msg.get("timestamp") or msg.get("data_timestamp") or ""
        ts = self._format_time(raw_ts)
        attachments = msg.get("attachments", [])
        # Normalize numbers
        if worker_number and not worker_number.startswith("+"):
            worker_number = "+" + worker_number
        if sender and not sender.startswith("+"):
            sender = "+" + sender
        logger.debug(f"_on_message: text='{text}', sender='{sender}', worker='{worker_number}'")
        is_sync = msg.get("is_sync", False)
        if is_sync:
            is_sent = True  # sent from a linked device
        else:
            is_sent = not sender or sender == worker_number
        display_name = sender if not is_sent else worker_number
        # For sync messages, display_name should be the recipient (sender = destination)
        if is_sync and sender:
            display_name = sender
        # Look up friendly name from contacts map (never show phone number)
        contact_info = self._contacts_map.get(display_name, {})
        friendly_name = contact_info.get("name", "")
        if not friendly_name:
            friendly_name = "Unknown"
            # Trigger background Supabase lookup
            self._resolve_client_name(display_name)
        logger.debug(f"_on_message: is_sent={is_sent}, display_name='{display_name}', friendly='{friendly_name}', active_chat='{self.active_chat}'")
        cache_key = display_name
        if cache_key not in self.messages_cache:
            self.messages_cache[cache_key] = []
        entry = {
            "text": text, "is_sent": is_sent, "time": ts, "sender": sender,
            "server_timestamp": raw_ts, "status": "delivered" if not is_sent else "sent",
            "attachments": attachments
        }
        if entry not in self.messages_cache[cache_key]:
            self.messages_cache[cache_key].append(entry)
            logger.debug(f"_on_message: cached under '{cache_key}', total {len(self.messages_cache[cache_key])}")
        if self.active_chat == display_name:
            logger.debug(f"_on_message: active chat matches, adding bubble")
            self.after(0, lambda t=text, s=is_sent, tm=ts, st="delivered" if not is_sent else "sent", att=attachments, sd=sender:
                       self._add_message_bubble(t, s, tm, st, att, sd, reactions=msg.get("reactions", [])))
        elif not is_sent:
            # Track unread for non-active chats
            self._unread_counts[display_name] = self._unread_counts.get(display_name, 0) + 1

        # Update sidebar preview immediately for this contact
        if not is_sent:
            messages = self.messages_cache.get(display_name, [])
            last_msg = messages[-1] if messages else None
            preview = last_msg.get("text", "")[:50] if last_msg else ""
            time_str = last_msg.get("time", "") if last_msg else ""
            unread = self._unread_counts.get(display_name, 0)
            if display_name in self._chat_widgets:
                w = self._chat_widgets[display_name]
                self.after(0, lambda w=w, p=preview, t=time_str, u=unread: (
                    w["preview_lbl"].configure(text=p),
                    w["time_lbl"].configure(text=t),
                    w["badge"].configure(text=str(u)),
                    w["badge"].place(x=28, y=-4) if u > 0 else w["badge"].place_forget()
                ))

        self._save_messages()
        # Download attachments in background
        if attachments and self.current_worker:
            import threading as _t
            _t.Thread(target=self._download_attachments,
                      args=(attachments, display_name, raw_ts), daemon=True).start()
        # Show notification for real incoming messages from contacts
        if not is_sent and text:
            self._play_notification()
            if friendly_name and friendly_name != "Unknown":
                self.after(0, lambda t=friendly_name, m=text[:80]: self._show_toast(f"New message from {t}", m))
            else:
                self.after(0, lambda m=text[:80]: self._show_toast("New message", m))
        # Handle incoming call
        call_info = msg.get("call")
        if call_info:
            call_type = call_info.get("type", "")
            call_id = call_info.get("callId", "")
            if call_type == "OFFER" and not is_sent and not self._call_popup:
                self._current_call_id = call_id
                self._call_contact = sender
                self.after(0, lambda s=sender, nm=friendly_name, cid=call_id: self._show_incoming_call(s, nm, cid))
                self.after(0, self._play_ringtone_loop)
            elif call_type == "HANGUP":
                self.after(0, self._close_call_popup)

    def _on_receipt(self, receipt: dict):
        logger.info(f"_on_receipt: {receipt}")
        r = receipt.get("receipt", {})
        timestamps = r.get("timestamps", [])
        is_read = r.get("isRead", False)
        status = "read" if is_read else "delivered"
        logger.info(f"_on_receipt: is_read={is_read}, {len(timestamps)} timestamps")
        for ts in timestamps:
            ts_str = str(ts)
            for chat_id, msgs in self.messages_cache.items():
                for msg in msgs:
                    if msg.get("server_timestamp") == ts_str and msg.get("is_sent"):
                        msg["status"] = status
                        logger.debug(f"Updated message status to {status}")
                        if self.active_chat == chat_id:
                            self.after(0, self._redisplay_messages)
                        break
        self._save_messages()

    def _on_typing(self, msg: dict):
        """Show/hide typing indicator when remote user is typing."""
        sender = msg.get("sender_id", "")
        action = msg.get("typing", {}).get("action", "STARTED")
        logger.info(f"_on_typing: sender='{sender}', action='{action}'")
        if sender != self.active_chat:
            return
        if action == "STARTED":
            self.typing_indicator.configure(text="typing...")
            self.typing_indicator.pack(side="left", padx=(4, 0))
            if self._typing_timer:
                self.after_cancel(self._typing_timer)
            self._typing_timer = self.after(5000, self._hide_typing_indicator)
        else:
            self._hide_typing_indicator()

    def _hide_typing_indicator(self):
        self.typing_indicator.pack_forget()
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
            self._typing_timer = None

    def _on_reaction(self, msg: dict):
        """Store reaction data on the cached message and redisplay if active."""
        reaction = msg.get("reaction", {})
        sender = msg.get("sender_id", "")
        target_ts = reaction.get("target_sent_timestamp", "")
        emoji = reaction.get("emoji", "")
        remove = reaction.get("remove", False)
        logger.info(f"_on_reaction: sender='{sender}', ts={target_ts}, emoji='{emoji}', remove={remove}")
        if not target_ts:
            return
        # Find the target message in cache
        for chat_id, msgs in self.messages_cache.items():
            for cached in msgs:
                if cached.get("server_timestamp") == target_ts:
                    if "reactions" not in cached:
                        cached["reactions"] = []
                    if remove:
                        cached["reactions"] = [r for r in cached["reactions"]
                                                if not (r.get("sender") == sender and r.get("emoji") == emoji)]
                    else:
                        # Update or append
                        existing = [r for r in cached["reactions"] if r.get("sender") == sender and r.get("emoji") == emoji]
                        if not existing:
                            cached["reactions"].append({"sender": sender, "emoji": emoji})
                    self._save_messages()
                    if self.active_chat == chat_id:
                        self.after(0, self._redisplay_messages)
                    return

    def _redisplay_messages(self):
        logger.info(f"_redisplay_messages: active_chat='{self.active_chat}'")
        if not self.active_chat:
            return
        self._last_bubble_sender = ""
        for w in self.messages_container.winfo_children():
            if w != self.no_chat_selected:
                w.destroy()
        self.no_chat_selected.pack_forget()
        msgs = self.messages_cache.get(self.active_chat, [])
        logger.info(f"_redisplay_messages: {len(msgs)} messages to display")
        for msg in msgs:
            downloaded = msg.get("downloaded", []) or msg.get("attachments", [])
            reactions = msg.get("reactions", [])
            self._add_message_bubble(msg.get("text", ""), msg.get("is_sent", True),
                                     msg.get("time", ""), msg.get("status", ""), downloaded,
                                     msg.get("sender", ""), reactions)
        # Scroll to bottom
        self.messages_container.update_idletasks()
        try:
            self.messages_container._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _update_chat_name_label(self, number: str, name: str):
        """Update the name label on an existing chat widget."""
        w = self._chat_widgets.get(number)
        if w and w.get("name_lbl"):
            w["name_lbl"].configure(text=name)

    def _resolve_client_name(self, number: str) -> None:
        """Look up client name from Supabase in a background thread, update _contacts_map."""
        if number in self._contacts_map and self._contacts_map[number].get("name"):
            return  # already have a name
        import threading as _t
        def lookup():
            try:
                client = self.supabase.get_client_by_real_id(number)
                if client:
                    name = client.masked_identity or "Unknown"
                    self.after(0, lambda n=number, nm=name: self._on_name_resolved(n, nm))
            except Exception as e:
                logger.info(f"_resolve_client_name error: {e}")
        _t.Thread(target=lookup, daemon=True).start()

    def _on_name_resolved(self, number: str, name: str):
        """Callback when Supabase name lookup completes."""
        if number not in self._contacts_map or not self._contacts_map[number].get("name"):
            self._contacts_map[number] = {"number": number, "name": name, "masked": True}
        # Update sidebar name label and avatar
        self._update_chat_name_label(number, name)
        w = self._chat_widgets.get(number)
        if w:
            w["name"] = name
            avatar_color = self._get_avatar_color(name)
            w["avatar"].configure(fg_color=avatar_color)
            w["initial_lbl"].configure(text=name[0].upper() if name else "#")
        # If this chat is currently open, update header
        if self.active_chat == number:
            self._active_chat_name = name
            self.chat_header_label.configure(text=name)
            # Update header avatar
            avatar_color = self._get_avatar_color(name)
            for w in self.chat_header_avatar.winfo_children():
                w.destroy()
            ha = ctk.CTkFrame(self.chat_header_avatar, width=36, height=36, corner_radius=18,
                               fg_color=avatar_color)
            ha.pack()
            ha.pack_propagate(False)
            ctk.CTkLabel(ha, text=name[0].upper() if name else "#", font=("Inter", 14, "bold"),
                          text_color="#FFFFFF").pack(expand=True)

    def _on_contacts(self, contacts: list):
        logger.info(f"_on_contacts called with {len(contacts)} contacts")
        import threading
        def load():
            try:
                logger.info(f"_on_contacts: user={self.current_user.id if self.current_user else 'None'}")
                office_id = self.current_user.office_id if self.current_user else None
                clients = self.supabase.get_clients_by_office(office_id) if office_id else []
                logger.info(f"_on_contacts: got {len(clients)} clients from supabase")
                seen = {c.get("number") for c in contacts}
                for c in clients:
                    num = c.real_identifier
                    if not num.startswith("+"):
                        num = "+" + num
                    name = c.masked_identity or "Unknown"
                    if num in seen:
                        for entry in contacts:
                            if entry.get("number") == num:
                                entry["name"] = name
                                entry["masked"] = True
                                break
                    else:
                        contacts.append({"number": num, "name": name, "masked": True})
                        seen.add(num)
            except Exception as e:
                logger.info(f"Error loading contacts: {e}")
                import traceback
                traceback.print_exc()
            logger.info(f"_on_contacts: update_chat_list with {len(contacts)} contacts")
            self.after(0, self._update_chat_list)
        threading.Thread(target=load, daemon=True).start()

    def _start_call(self):
        logger.info(f"_start_call: active_chat='{self.active_chat}', worker={'yes' if self.current_worker else 'no'}")
        if not self.active_chat or not self.current_worker:
            return
        if self._call_popup is not None:
            logger.info("_start_call: popup already open")
            return
        self._call_state = "calling"
        self._call_contact = self.active_chat
        self._call_display_name = self._active_chat_name or "Unknown"
        self._show_call_popup(f"Calling {self._call_display_name}...", outgoing=True)
        self._play_ringtone_loop()
        import threading, asyncio
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                svc = self.current_worker.service
                # Stop daemon if running — it would conflict with direct startCall/acceptCall
                logger.info(f"_start_call: stopping daemon if running")
                if svc._process:
                    loop.run_until_complete(svc.stop_daemon())
                # Suspend receive loop so it doesn't hold the config lock during the call
                svc._suspend_receive = True
                # Wait for any in-flight receive to finish releasing config lock
                import time; time.sleep(2)
                try:
                    logger.info(f"_start_call: running startCall to {self.active_chat}")
                    out, err, rc = loop.run_until_complete(
                        svc._run_async(
                            ["-u", svc.number, "startCall", self.active_chat], timeout=3600
                        )
                    )
                finally:
                    svc._suspend_receive = False
                logger.info(f"_start_call: startCall rc={rc}, out='{out[:200]}', err='{err[:200]}'")
                for line in (out + err).splitlines():
                    if "Call ID:" in line:
                        cid = line.split("Call ID:")[-1].strip()
                        if cid:
                            self._current_call_id = cid
                            break
                if rc == 0:
                    self._call_state = "in_call"
                    self.after(0, lambda: self._show_call_popup(f"Calling {self._call_display_name}...", outgoing=True))
                else:
                    self.after(0, self._close_call_popup)
            except Exception as e:
                logger.info(f"Call error: {e}")
                import traceback; traceback.print_exc()
                self.after(0, self._close_call_popup)
            loop.close()
        threading.Thread(target=run, daemon=True).start()

    def _show_call_popup(self, text: str, outgoing: bool = False):
        self._close_call_popup()
        popup = ctk.CTkToplevel(self)
        popup.title("Signal Call")
        popup.geometry("320x220")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.transient(self)
        popup.configure(fg_color=BG)
        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 320) // 2
        y = self.winfo_y() + (self.winfo_height() - 220) // 2
        popup.geometry(f"320x220+{x}+{y}")
        ctk.CTkLabel(popup, text=text, font=("Inter", 16, "bold"),
                      text_color=TEXT_PRIMARY).pack(pady=(30, 5))
        contact = self._call_display_name or self._active_chat_name or "Unknown"
        ctk.CTkLabel(popup, text=contact, font=("Inter", 13),
                      text_color=TEXT_SECONDARY).pack(pady=(0, 15))
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack()
        if outgoing:
            ctk.CTkButton(btn_frame, text="Hang Up", width=100, height=36,
                           font=("Inter", 13), corner_radius=18,
                           fg_color="#f44336", hover_color="#d32f2f",
                           command=self._hangup_call).pack(pady=10)
        else:
            ctk.CTkButton(btn_frame, text="Accept", width=90, height=36,
                           font=("Inter", 13), corner_radius=18,
                           fg_color="#4CAF50", hover_color="#388E3C",
                           command=lambda: self._accept_call(self._call_contact)).pack(side="left", padx=5)
            ctk.CTkButton(btn_frame, text="Decline", width=90, height=36,
                           font=("Inter", 13), corner_radius=18,
                           fg_color="#f44336", hover_color="#d32f2f",
                           command=self._reject_call).pack(side="left", padx=5)
        self._call_popup = popup
        popup.protocol("WM_DELETE_WINDOW", lambda: self._close_call_popup())

    def _show_incoming_call(self, sender: str, display_name: str, call_id: str):
        self._call_contact = sender
        self._current_call_id = call_id
        self._call_state = "ringing"
        self._call_display_name = display_name
        self._show_call_popup(f"Incoming call...", outgoing=False)

    def _accept_call(self, sender: str):
        logger.info(f"_accept_call: sender='{sender}', call_id='{self._current_call_id}'")
        self._stop_sound()
        self._call_state = "in_call"
        self._close_call_popup()
        import threading, asyncio
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                svc = self.current_worker.service
                # Stop daemon if running — it would conflict with direct acceptCall
                logger.info(f"_accept_call: stopping daemon if running")
                if svc._process:
                    loop.run_until_complete(svc.stop_daemon())
                # Suspend receive loop so it doesn't hold the config lock during the call
                svc._suspend_receive = True
                # Wait for any in-flight receive to finish releasing config lock
                import time; time.sleep(2)
                try:
                    logger.info(f"_accept_call: running acceptCall --call-id {self._current_call_id}")
                    out, err, rc = loop.run_until_complete(
                        svc._run_async(
                            ["-u", svc.number, "acceptCall",
                             "--call-id", self._current_call_id or ""], timeout=3600
                        )
                    )
                    logger.info(f"_accept_call: rc={rc}, out='{out[:200]}', err='{err[:200]}'")
                    if rc == 0:
                        self._call_state = "in_call"
                        display = self._call_display_name or "Unknown"
                        self.after(0, lambda d=display: self._show_call_popup(f"In call with {d}", outgoing=True))
                    else:
                        self.after(0, self._close_call_popup)
                finally:
                    svc._suspend_receive = False
            except Exception as e:
                logger.info(f"_accept_call error: {e}")
                import traceback; traceback.print_exc()
                self.after(0, self._close_call_popup)
            loop.close()
        threading.Thread(target=run, daemon=True).start()

    def _reject_call(self):
        logger.info(f"_reject_call: call_id='{self._current_call_id}'")
        self._stop_sound()
        self._call_state = None
        import threading, asyncio
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.current_worker.service._run_async(
                        ["-u", self.current_worker.service.number, "rejectCall",
                         "--call-id", self._current_call_id or ""], timeout=15
                    )
                )
            except Exception:
                pass
            loop.close()
            self.after(0, self._close_call_popup)
        threading.Thread(target=run, daemon=True).start()

    def _hangup_call(self):
        logger.info(f"_hangup_call: call_id='{self._current_call_id}'")
        self._stop_sound()
        self._call_state = None
        import threading, asyncio
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.current_worker.service._run_async(
                        ["-u", self.current_worker.service.number, "hangupCall",
                         "--call-id", self._current_call_id or ""], timeout=15
                    )
                )
            except Exception:
                pass
            loop.close()
            self.after(0, self._close_call_popup)
        threading.Thread(target=run, daemon=True).start()

    def _show_message_search(self):
        """Open a search dialog for the current chat's messages."""
        if not self.active_chat or not self.messages_cache.get(self.active_chat):
            return
        msgs = self.messages_cache[self.active_chat]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Search Messages")
        dialog.geometry("400x500")
        dialog.transient(self)
        dialog.configure(fg_color=BG)
        ctk.CTkLabel(dialog, text="Search in conversation",
                      font=("Inter", 14, "bold"), text_color=TEXT_PRIMARY).pack(pady=(12, 5))
        search_entry = ctk.CTkEntry(dialog, placeholder_text="Search...",
                                     height=36, fg_color=SEARCH_BG, border_width=0,
                                     corner_radius=18, placeholder_text_color=TEXT_SECONDARY)
        search_entry.pack(fill="x", padx=16, pady=(0, 8))
        results_frame = ctk.CTkScrollableFrame(dialog, fg_color="transparent", corner_radius=0)
        results_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        no_results = ctk.CTkLabel(results_frame, text="", font=("Inter", 12), text_color=TEXT_SECONDARY)
        no_results.pack(pady=20)

        def do_search(event=None):
            query = search_entry.get().strip().lower()
            for w in list(results_frame.winfo_children()):
                if w is not no_results:
                    w.destroy()
            if not query:
                no_results.configure(text="Type to search")
                no_results.pack(pady=20)
                return
            matches = [m for m in msgs if query in m.get("text", "").lower()]
            if not matches:
                no_results.configure(text="No messages found")
                no_results.pack(pady=20)
                return
            no_results.pack_forget()
            for m in matches:
                preview = m.get("text", "")[:120]
                is_sent = m.get("is_sent", True)
                t = m.get("time", "")
                card = ctk.CTkFrame(results_frame, fg_color=SENT_BUBBLE if is_sent else RECEIVED_BUBBLE,
                                    corner_radius=12)
                card.pack(fill="x", padx=4, pady=2)
                ctk.CTkLabel(card, text=preview, font=("Inter", 12),
                              text_color="#FFFFFF" if is_sent else TEXT_PRIMARY,
                              wraplength=320, justify="left", anchor="w").pack(padx=12, pady=(8, 2))
                if t:
                    ctk.CTkLabel(card, text=t, font=("Inter", 10),
                                  text_color="#B0B0B0" if is_sent else TEXT_SECONDARY).pack(anchor="e", padx=12, pady=(0, 6))

        search_entry.bind("<KeyRelease>", do_search)
        dialog.focus()

    def _send_read_receipts(self, contact: str, timestamps: list):
        """Send read receipts for the given timestamps in a background thread."""
        if not timestamps or not self.current_worker:
            return
        # Filter out timestamps already in-flight or already sent
        new_ts = [ts for ts in timestamps if ts not in self._pending_read_receipts]
        if not new_ts:
            return
        for ts in new_ts:
            self._pending_read_receipts.add(ts)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(
                self.current_worker.service.send_receipt(contact, new_ts, "read")
            )
            if success:
                for ts in new_ts:
                    msgs = self.messages_cache.get(contact, [])
                    for m in msgs:
                        if m.get("server_timestamp") == ts and m.get("is_sent"):
                            m["read_receipt_sent"] = True
                self._save_messages()
        except Exception as e:
            logger.info(f"_send_read_receipts error: {e}")
        finally:
            for ts in new_ts:
                self._pending_read_receipts.discard(ts)
            loop.close()

    def _close_call_popup(self):
        logger.info("_close_call_popup")
        self._stop_sound()
        if self._call_popup:
            try:
                self._call_popup.destroy()
            except Exception:
                pass
            self._call_popup = None
        # Ensure receive loop is not stuck suspended
        if self.current_worker and self.current_worker.service:
            self.current_worker.service._suspend_receive = False

    def _attach_file(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(title="Select file to send")
        if not filepath or not self.active_chat or not self.current_worker:
            return
        self._show_loading("Uploading file...")
        from datetime import datetime
        now_ms = str(int(datetime.now().timestamp() * 1000))
        ts = self._format_time(now_ms)
        filename = os.path.basename(filepath)
        ct, _ = mimetypes.guess_type(filepath)
        if not ct:
            ct = "application/octet-stream"
        att = {"path": filepath, "contentType": ct}
        self._add_message_bubble("", True, ts, "sent", [att])
        if self.active_chat not in self.messages_cache:
            self.messages_cache[self.active_chat] = []
        self.messages_cache[self.active_chat].append({
            "text": filename, "is_sent": True, "time": ts, "sender": "",
            "server_timestamp": now_ms, "status": "sent", "attachments": [dict(att)]
        })
        self._save_messages()
        def _on_file_done():
            self.after(0, self._hide_loading)
        self.current_worker.send_file(self.active_chat, filepath, on_done=_on_file_done)

    def _on_user_typing(self):
        """Send typing indicator with 3s rate-limit; debounce stop after 2s idle."""
        if not self.active_chat or not self.current_worker:
            return
        now = time.time()
        if now - self._last_typing_sent < 3.0:
            pass  # rate-limited, but still restart the stop timer
        else:
            self._last_typing_sent = now
            self.current_worker.send_typing(self.active_chat, stop=False)
        if self._typing_debounce:
            self.after_cancel(self._typing_debounce)
        self._typing_debounce = self.after(2000, self._stop_typing)

    def _stop_typing(self):
        if self.active_chat and self.current_worker:
            self.current_worker.send_typing(self.active_chat, stop=True)
        self._typing_debounce = None

    def _send_message(self):
        self._stop_typing()
        text = self.message_entry.get().strip()
        if not text or not self.active_chat or not self.current_worker:
            return
        self.message_entry.delete(0, "end")
        from datetime import datetime
        now_ms = str(int(datetime.now().timestamp() * 1000))
        ts = self._format_time(now_ms)
        self._add_message_bubble(text, True, ts, "sent")
        if self.active_chat not in self.messages_cache:
            self.messages_cache[self.active_chat] = []
        self.messages_cache[self.active_chat].append({
            "text": text, "is_sent": True, "time": ts, "sender": "",
            "server_timestamp": now_ms, "status": "sent"
        })
        self._save_messages()
        self.current_worker.send_message(self.active_chat, text)


# ===================== SIGNAL WORKER =====================

class SignalWorker:
    def __init__(self, number: str):
        self.service = SignalService(number)
        self.on_connected = None
        self.on_disconnected = None
        self.on_message = None
        self.on_receipt = None
        self.on_typing = None
        self.on_reaction = None
        self.on_contacts = None
        self._contacts_cache: Optional[list] = None
        self._loop = None
        self._thread = None

    def connect(self):
        logger.debug(f"connect: number='{self.service.number}'")
        def run():
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self.service.on("on_message", lambda m: self.on_message and self.on_message(m))
            self.service.on("on_receipt", lambda m: self.on_receipt and self.on_receipt(m))
            self.service.on("on_typing", lambda m: self.on_typing and self.on_typing(m))
            self.service.on("on_reaction", lambda m: self.on_reaction and self.on_reaction(m))
            try:
                success = self._loop.run_until_complete(self.service.connect())
                logger.debug(f"connect: success={success}")
                if success:
                    if self.on_connected:
                        self.on_connected()
                    self._load_contacts()
                    self._loop.run_forever()
                else:
                    logger.debug("connect: failed")
                    self._cleanup_loop()
            except Exception as e:
                logger.debug(f"connect error: {e}")
                self._cleanup_loop()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def _load_contacts(self):
        def load():
            logger.debug("_load_contacts started")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                contacts = loop.run_until_complete(self.service.get_contacts()) or []
                logger.debug(f"get_contacts returned: {contacts}")
                self._contacts_cache = contacts
                if self.on_contacts:
                    logger.debug("calling on_contacts")
                    self.on_contacts(contacts)
                else:
                    logger.debug("on_contacts is None!")
            except Exception as e:
                logger.debug(f"_load_contacts error: {e}")
                self._contacts_cache = []
                if self.on_contacts:
                    self.on_contacts([])
            finally:
                loop.close()
        threading.Thread(target=load, daemon=True).start()

    def disconnect(self):
        logger.debug(f"disconnect: number='{self.service.number}'")
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.service.disconnect(), self._loop)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self.on_disconnected:
            self.on_disconnected()

    def send_message(self, recipient: str, text: str):
        logger.debug(f"send_message: to='{recipient}', text='{text[:50]}'")
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.service.send_message(recipient, text), self._loop
            )

    def send_typing(self, recipient: str, stop: bool = False):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.service.send_typing(recipient, stop), self._loop
            )

    def send_file(self, recipient: str, filepath: str, message: str = "", on_done=None):
        logger.debug(f"send_file: to='{recipient}', file='{filepath}'")
        if self._loop and self._loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(
                self.service.send_file(recipient, filepath, message), self._loop
            )
            if on_done:
                def _wait():
                    fut.result()
                    on_done()
                threading.Thread(target=_wait, daemon=True).start()

    def _cleanup_loop(self):
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.stop()
                self._loop.close()
            except Exception:
                pass
        self._loop = None


if __name__ == "__main__":
    app = SignalApp()
    app.mainloop()
