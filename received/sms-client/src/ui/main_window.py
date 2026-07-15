import customtkinter as ctk
from tkinter import messagebox
from src.services.supabase_service import SupabaseService
from src.models.schemas import StaffAssignment, User
import threading
import json
import urllib.request
import time
from datetime import datetime


class SMSApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SMS Staff")
        self.geometry("1100x700")
        self.configure(fg_color="#0a0a1a")
        self.supabase = SupabaseService()
        self.current_user = None
        self._clients = []
        self._selected_client = None
        self._chat_messages = {}
        self._gateway = None
        self._sms_gateway = "default"
        self._show_login()

    def _show_login(self):
        self.clear()
        frame = ctk.CTkFrame(self, fg_color="#0a0a1a")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="SMS Staff", font=("Arial", 36, "bold"),
                    text_color="#e94560").pack(pady=(0, 5))
        ctk.CTkLabel(frame, text="Login to continue", font=("Arial", 14),
                    text_color="#666").pack(pady=(0, 30))

        self.email_entry = ctk.CTkEntry(frame, placeholder_text="Email",
                                        width=320, height=42, corner_radius=8,
                                        fg_color="#16213e", border_color="#16213e",
                                        font=("Arial", 13))
        self.email_entry.pack(pady=5)
        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Password", show="*",
                                           width=320, height=42, corner_radius=8,
                                           fg_color="#16213e", border_color="#16213e",
                                           font=("Arial", 13))
        self.password_entry.pack(pady=5)
        self.password_entry.bind("<Return>", lambda e: self._login())

        self.login_btn = ctk.CTkButton(frame, text="Login", width=320, height=42,
                                       corner_radius=8, fg_color="#e94560",
                                       hover_color="#c81e45", font=("Arial", 14, "bold"),
                                       command=self._login)
        self.login_btn.pack(pady=15)

        self.login_status = ctk.CTkLabel(frame, text="", font=("Arial", 12))
        self.login_status.pack()

    def _login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            self.login_status.configure(text="Enter email and password", text_color="#f44336")
            return
        self.login_btn.configure(state="disabled", text="Logging in...")
        self.login_status.configure(text="")

        def do_login():
            user = self.supabase.login(email, password)
            self.after(0, lambda: self._on_login_result(user))

        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_result(self, user):
        if user:
            self.current_user = user
            self._show_main()
        else:
            self.login_btn.configure(state="normal", text="Login")
            self.login_status.configure(text="Invalid credentials", text_color="#f44336")

    def _show_main(self):
        self.clear()
        self.configure(fg_color="#0a0a1a")

        left = ctk.CTkFrame(self, width=320, fg_color="#0f1629", corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        top = ctk.CTkFrame(left, fg_color="#0f1629", height=65)
        top.pack(fill="x")
        top.pack_propagate(False)
        top_inner = ctk.CTkFrame(top, fg_color="transparent")
        top_inner.pack(fill="both", expand=True, padx=15, pady=12)

        ctk.CTkLabel(top_inner, text="SMS Staff", font=("Arial", 20, "bold"),
                    text_color="#e94560").pack(side="left")

        status_color = "#4CAF50" if self._is_connected() else "#f44336"
        status_text = "Connected" if self._is_connected() else "Disconnected"
        self.sidebar_status = ctk.CTkLabel(top_inner, text=f"  {status_text}",
                                          font=("Arial", 11), text_color=status_color)
        self.sidebar_status.pack(side="right")

        search = ctk.CTkFrame(left, fg_color="transparent")
        search.pack(fill="x", padx=12, pady=(0, 8))
        self.contact_search = ctk.CTkEntry(search, placeholder_text="Search...",
                                          height=34, corner_radius=17,
                                          fg_color="#16213e", border_color="#16213e",
                                          font=("Arial", 12))
        self.contact_search.pack(fill="x")
        self.contact_search.bind("<KeyRelease>", lambda e: self._filter_contacts())

        self.contact_list = ctk.CTkScrollableFrame(left, fg_color="transparent",
                                                     scrollbar_button_color="#16213e",
                                                     scrollbar_button_hover_color="#1a2744")
        self.contact_list.pack(fill="both", expand=True, padx=6)

        bottom = ctk.CTkFrame(left, fg_color="#0f1629", height=50)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        conn_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        conn_frame.pack(fill="x", padx=12, pady=8)
        ctk.CTkButton(conn_frame, text="Connect Phone", width=100, height=30, corner_radius=6,
                      fg_color="#16213e", hover_color="#1a2744",
                      font=("Arial", 11), command=self._show_connect_dialog).pack(side="left")
        ctk.CTkButton(conn_frame, text="Logout", width=60, height=30, corner_radius=6,
                      fg_color="#16213e", hover_color="#d32f2f",
                      font=("Arial", 11), command=self._logout).pack(side="right")

        right = ctk.CTkFrame(self, fg_color="#0a0a1a", corner_radius=0)
        right.pack(side="right", fill="both", expand=True)

        self.chat_header = ctk.CTkFrame(right, fg_color="#0f1629", height=65, corner_radius=0)
        self.chat_header.pack(fill="x")
        self.chat_header.pack_propagate(False)
        h_inner = ctk.CTkFrame(self.chat_header, fg_color="transparent")
        h_inner.pack(fill="both", expand=True, padx=15, pady=10)

        self.chat_avatar = ctk.CTkLabel(h_inner, text="?", width=42, height=42,
                                        corner_radius=21, fg_color="#16213e",
                                        font=("Arial", 17, "bold"), text_color="#fff")
        self.chat_avatar.pack(side="left", padx=(0, 12))
        name_frame = ctk.CTkFrame(h_inner, fg_color="transparent")
        name_frame.pack(side="left")
        self.chat_title = ctk.CTkLabel(name_frame, text="Select a contact",
                                       font=("Arial", 15, "bold"), text_color="#fff", anchor="w")
        self.chat_title.pack(anchor="w")
        self.chat_subtitle = ctk.CTkLabel(name_frame, text="",
                                         font=("Arial", 11), text_color="#666", anchor="w")
        self.chat_subtitle.pack(anchor="w")

        call_frame = ctk.CTkFrame(h_inner, fg_color="transparent")
        call_frame.pack(side="right")
        self.call_btn = ctk.CTkButton(call_frame, text="Call", width=65, height=32,
                                      corner_radius=8, fg_color="#4CAF50", hover_color="#388E3C",
                                      font=("Arial", 12, "bold"), command=self._make_call)
        self.call_btn.pack(side="left", padx=3)
        self.hangup_btn = ctk.CTkButton(call_frame, text="End", width=55, height=32,
                                        corner_radius=8, fg_color="#f44336", hover_color="#d32f2f",
                                        font=("Arial", 12, "bold"), command=self._end_call)
        self.hangup_btn.pack(side="left", padx=3)

        self.messages_frame = ctk.CTkScrollableFrame(right, fg_color="#0a0a1a",
                                                      scrollbar_button_color="#16213e")
        self.messages_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.empty_label = ctk.CTkLabel(self.messages_frame,
            text="Select a contact to start messaging",
            font=("Arial", 14), text_color="#444")
        self.empty_label.pack(expand=True, pady=120)

        input_frame = ctk.CTkFrame(right, fg_color="#0f1629", height=60, corner_radius=0)
        input_frame.pack(fill="x")
        input_frame.pack_propagate(False)
        inp = ctk.CTkFrame(input_frame, fg_color="transparent")
        inp.pack(fill="x", padx=12, pady=12)
        self.message_entry = ctk.CTkEntry(inp, placeholder_text="Type a message...",
                                         height=36, corner_radius=18,
                                         fg_color="#16213e", border_color="#16213e",
                                         font=("Arial", 13))
        self.message_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.message_entry.bind("<Return>", lambda e: self._send_sms())
        self.send_btn = ctk.CTkButton(inp, text="Send", width=65, height=36,
                                      corner_radius=18, fg_color="#e94560",
                                      hover_color="#c81e45", font=("Arial", 13, "bold"),
                                      command=self._send_sms)
        self.send_btn.pack(side="right")

        self.phone_entry = ctk.CTkEntry(right)
        self.phone_entry.pack_forget()

        self._load_contacts()

    def _logout(self):
        if self._gateway:
            self._gateway.stop()
            self._gateway = None
        self._show_login()

    def _is_connected(self):
        return self._gateway is not None and self._gateway.connected

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _load_contacts(self):
        if not self.current_user:
            return
        threading.Thread(target=self._fetch_contacts, daemon=True).start()

    def _fetch_contacts(self):
        try:
            office_id = self.current_user.office_id if self.current_user else None
            assignments = self.supabase.get_staff_assignments(self.current_user.id, "sms") if self.current_user else []
            self._sms_gateway = assignments[0].gateway_number if assignments else "default"
            clients = self.supabase.get_clients_by_office(office_id, self._sms_gateway) if office_id else []
            self._clients = clients
            self.after(0, self._render_contacts)
        except Exception:
            pass

    def _render_contacts(self, filter_text=""):
        for w in self.contact_list.winfo_children():
            w.destroy()
        filtered = self._clients
        if filter_text:
            filtered = [c for c in self._clients
                       if filter_text.lower() in c.masked_identity.lower()]
        if not filtered:
            ctk.CTkLabel(self.contact_list, text="No contacts",
                        font=("Arial", 12), text_color="#444").pack(pady=20)
            return
        for client in filtered:
            self._contact_card(client)

    def _contact_card(self, client):
        sel = self._selected_client and self._selected_client.id == client.id
        bg = "#16213e" if sel else "transparent"

        card = ctk.CTkFrame(self.contact_list, fg_color=bg, corner_radius=10, height=58)
        card.pack(fill="x", padx=3, pady=2)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=9)

        name = client.masked_identity
        initial = name[0].upper() if name else "?"
        colors = ["#e94560", "#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#00BCD4", "#FF5722"]
        ci = sum(ord(c) for c in name) % len(colors)

        ctk.CTkLabel(inner, text=initial, width=38, height=38,
                    corner_radius=19, fg_color=colors[ci],
                    font=("Arial", 15, "bold"), text_color="#fff").pack(side="left", padx=(0, 10))

        tf = ctk.CTkFrame(inner, fg_color="transparent")
        tf.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(tf, text=name, font=("Arial", 13, "bold"),
                    text_color="#fff", anchor="w").pack(anchor="w")
        ctk.CTkLabel(tf, text="phone hidden",
                    font=("Arial", 11), text_color="#666", anchor="w").pack(anchor="w")

        msgs = self._chat_messages.get(client.id, [])
        if msgs:
            last = msgs[-1]
            preview = last["message"][:25] + ("..." if len(last["message"]) > 25 else "")
            pf = ctk.CTkFrame(card, fg_color="transparent")
            pf.pack(side="right", padx=5)
            ctk.CTkLabel(pf, text=last.get("time", ""), font=("Arial", 9),
                        text_color="#666").pack(anchor="e")
            ctk.CTkLabel(pf, text=preview, font=("Arial", 10),
                        text_color="#888", wraplength=100).pack(anchor="e")

        def click(e, c=client):
            self._select_contact(c)
        card.bind("<Button-1>", click)
        for w in [inner, tf] + tf.winfo_children():
            w.bind("<Button-1>", click)

    def _select_contact(self, client):
        self._selected_client = client
        self.phone_entry.delete(0, "end")
        self.phone_entry.insert(0, client.identifier_for("sms"))

        initial = client.masked_identity[0].upper() if client.masked_identity else "?"
        self.chat_avatar.configure(text=initial)
        self.chat_title.configure(text=client.masked_identity)
        self.chat_subtitle.configure(text="phone hidden")
        self.empty_label.pack_forget()
        self._render_chat()
        for w in self.contact_list.winfo_children():
            w.destroy()
        for c in self._clients:
            self._contact_card(c)

    def _render_chat(self):
        for w in self.messages_frame.winfo_children():
            if w != self.empty_label:
                w.destroy()
        if not self._selected_client:
            return
        msgs = self._chat_messages.get(self._selected_client.id, [])
        if not msgs:
            ctk.CTkLabel(self.messages_frame, text="No messages yet",
                        font=("Arial", 12), text_color="#444").pack(pady=60)
            return
        for msg in msgs:
            self._bubble(msg)

    def _bubble(self, msg):
        sent = msg.get("direction") == "sent"
        text = msg.get("message", "")
        ts = msg.get("time", "")

        wrap = ctk.CTkFrame(self.messages_frame, fg_color="transparent")
        wrap.pack(fill="x", padx=10, pady=2)

        if sent:
            b = ctk.CTkFrame(wrap, fg_color="#e94560", corner_radius=16)
            b.pack(anchor="e", padx=(80, 0))
        else:
            b = ctk.CTkFrame(wrap, fg_color="#16213e", corner_radius=16)
            b.pack(anchor="w", padx=(0, 80))

        ctk.CTkLabel(b, text=text, font=("Arial", 13), text_color="#fff",
                    wraplength=350, justify="left", anchor="w").pack(padx=14, pady=(8, 1))
        if ts:
            ctk.CTkLabel(b, text=ts, font=("Arial", 9),
                        text_color="#aaaaaa").pack(padx=14, pady=(0, 7), anchor="e")

    def _filter_contacts(self):
        self._render_contacts(self.contact_search.get().strip())

    def _send_sms(self):
        if not self._is_connected():
            messagebox.showerror("Error", "No phone connected.")
            return
        phone = self.phone_entry.get().strip()
        text = self.message_entry.get().strip()
        if not phone or not text:
            return
        sent = self._gateway.send_sms(phone, text)
        if sent:
            now = datetime.now().strftime("%H:%M")
            msg = {"direction": "sent", "message": text, "time": now}
            cid = self._selected_client.id if self._selected_client else phone
            if cid not in self._chat_messages:
                self._chat_messages[cid] = []
            self._chat_messages[cid].append(msg)
            self._render_chat()
            self.message_entry.delete(0, "end")
        else:
            messagebox.showerror("Error", "Failed to send SMS.")

    def _make_call(self):
        if not self._is_connected():
            messagebox.showerror("Error", "No phone connected.")
            return
        phone = self.phone_entry.get().strip()
        if not phone:
            return
        self._gateway.make_call(phone)

    def _end_call(self):
        if self._is_connected():
            self._gateway.end_call()

    def _show_connect_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Connect Phone")
        dialog.geometry("450x350")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color="#0a0a1a")

        ctk.CTkLabel(dialog, text="Connect Your Phone",
                    font=("Arial", 18, "bold"), text_color="#e94560").pack(pady=(20, 15))

        ctk.CTkLabel(dialog,
            text="Both methods give full SMS + Call control.\n"
                 "Your phone must be on the same WiFi network.",
            font=("Arial", 12), text_color="#888", justify="center").pack(pady=(0, 15))

        btn_style = {"width": 380, "height": 50, "corner_radius": 10,
                     "font": ("Arial", 14, "bold")}

        ctk.CTkButton(dialog, text="Method 1: Termux (Android)",
                      fg_color="#16213e", hover_color="#1a2744",
                      command=lambda: [dialog.destroy(), self._connect_termux()],
                      **btn_style).pack(pady=8)

        ctk.CTkButton(dialog, text="Method 2: HTTP Gateway App",
                      fg_color="#16213e", hover_color="#1a2744",
                      command=lambda: [dialog.destroy(), self._connect_http_app()],
                      **btn_style).pack(pady=8)

    def _validate_phone_assignment(self, phone_number: str) -> bool:
        if not self.current_user:
            return False
        assignments = self.supabase.get_staff_assignments(self.current_user.id, "sms")
        if not assignments:
            messagebox.showerror("Error", "No SMS assignments found for your account. Contact your manager.")
            return False
        phone_clean = phone_number.replace("+", "").replace("-", "").replace(" ", "")
        valid_numbers = [a.phone_number for a in assignments if a.is_active]
        matched = any(
            vn.replace("+", "").replace("-", "").replace(" ", "") == phone_clean
            for vn in valid_numbers
        )
        if not matched:
            messagebox.showerror("Error",
                f"This phone number is not assigned to you.\n\n"
                f"Your assigned numbers: {', '.join(valid_numbers) if valid_numbers else 'None'}\n\n"
                f"Contact your manager to assign this number.")
            return False
        return True

    def _connect_termux(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Termux Connection")
        dialog.geometry("500x530")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color="#0a0a1a")

        ctk.CTkLabel(dialog, text="Android + Termux",
                    font=("Arial", 16, "bold"), text_color="#fff").pack(pady=(15, 5))
        ctk.CTkLabel(dialog,
            text="Setup on your Android phone:\n\n"
                 "1. Install Termux from F-Droid (NOT Play Store)\n"
                 "2. Open Termux, run:\n"
                 "   pkg install python\n"
                 "   pkg install termux-api\n"
                 "3. Install Termux:API from F-Droid\n"
                 "4. Copy phone_server.py to your phone\n"
                 "5. Run: python phone_server.py\n"
                 "6. Enter the URL shown on your phone below",
            font=("Arial", 11), text_color="#888", justify="left").pack(pady=5, padx=30, anchor="w")

        url = ctk.CTkEntry(dialog, placeholder_text="http://192.168.1.100:8080",
                          width=400, height=38, fg_color="#16213e", border_color="#16213e")
        url.pack(pady=10)
        ctk.CTkLabel(dialog, text="Phone number on this device:", font=("Arial", 11), text_color="#888", anchor="w").pack(fill="x", padx=30)
        phone_entry = ctk.CTkEntry(dialog, placeholder_text="+1234567890",
                                   width=400, height=38, fg_color="#16213e", border_color="#16213e")
        phone_entry.pack(pady=5)
        st = ctk.CTkLabel(dialog, text="", font=("Arial", 11))
        st.pack(pady=3)

        def go():
            phone = phone_entry.get().strip()
            if not phone:
                st.configure(text="Enter your phone number", text_color="#f44336")
                return
            if not self._validate_phone_assignment(phone):
                return
            u = url.get().strip()
            if not u:
                st.configure(text="Enter URL from phone", text_color="#f44336")
                return
            if not u.startswith("http"):
                u = f"http://{u}"
            st.configure(text="Connecting...", text_color="#FF9800")

            def do():
                gw = PhoneGateway()
                ok = gw.connect(u)
                dialog.after(0, lambda: done(ok, gw))
            threading.Thread(target=do, daemon=True).start()

        def done(ok, gw):
            if not ok:
                st.configure(text="Cannot connect. Is phone_server.py running?",
                           text_color="#f44336")
                return
            self._gateway = gw
            gw.start_polling(self._on_message)
            self._update_status()
            dialog.destroy()
            messagebox.showinfo("Connected", "Phone connected via Termux!")

        ctk.CTkButton(dialog, text="Connect", fg_color="#4CAF50", hover_color="#388E3C",
                      command=go).pack(pady=10)

    def _connect_http_app(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("HTTP Gateway App")
        dialog.geometry("500x530")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color="#0a0a1a")

        ctk.CTkLabel(dialog, text="HTTP Gateway App",
                    font=("Arial", 16, "bold"), text_color="#fff").pack(pady=(15, 5))
        ctk.CTkLabel(dialog,
            text="Setup on your Android phone:\n\n"
                 "1. Install 'SMS Gateway' from Play Store\n"
                 "2. Open the app and start the server\n"
                 "3. It will show an IP address and port\n"
                 "4. Enter that address below",
            font=("Arial", 11), text_color="#888", justify="left").pack(pady=5, padx=30, anchor="w")

        url = ctk.CTkEntry(dialog, placeholder_text="http://192.168.1.100:8080",
                          width=400, height=38, fg_color="#16213e", border_color="#16213e")
        url.pack(pady=10)
        ctk.CTkLabel(dialog, text="Phone number on this device:", font=("Arial", 11), text_color="#888", anchor="w").pack(fill="x", padx=30)
        phone_entry = ctk.CTkEntry(dialog, placeholder_text="+1234567890",
                                   width=400, height=38, fg_color="#16213e", border_color="#16213e")
        phone_entry.pack(pady=5)
        st = ctk.CTkLabel(dialog, text="", font=("Arial", 11))
        st.pack(pady=3)

        def go():
            phone = phone_entry.get().strip()
            if not phone:
                st.configure(text="Enter your phone number", text_color="#f44336")
                return
            if not self._validate_phone_assignment(phone):
                return
            u = url.get().strip()
            if not u:
                st.configure(text="Enter URL from app", text_color="#f44336")
                return
            if not u.startswith("http"):
                u = f"http://{u}"
            st.configure(text="Connecting...", text_color="#FF9800")

            def do():
                gw = PhoneGateway()
                ok = gw.connect(u)
                dialog.after(0, lambda: done(ok, gw))
            threading.Thread(target=do, daemon=True).start()

        def done(ok, gw):
            if not ok:
                st.configure(text="Cannot connect. Is the app running?",
                           text_color="#f44336")
                return
            self._gateway = gw
            gw.start_polling(self._on_message)
            self._update_status()
            dialog.destroy()
            messagebox.showinfo("Connected", "Phone connected via HTTP App!")

        ctk.CTkButton(dialog, text="Connect", fg_color="#4CAF50", hover_color="#388E3C",
                      command=go).pack(pady=10)

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
            toast.configure(fg_color="#16213e")
            px = self.winfo_x() + self.winfo_width() - 340
            py = self.winfo_y() + 60
            toast.geometry(f"320x80+{px}+{py}")
            ctk.CTkLabel(toast, text=title, font=("Arial", 12, "bold"), text_color="#e94560", anchor="w").pack(fill="x", padx=12, pady=(8, 0))
            ctk.CTkLabel(toast, text=message, font=("Arial", 11), text_color="#cccccc", anchor="w", wraplength=280).pack(fill="x", padx=12, pady=(2, 8))
            toast.after(duration, toast.destroy)
        except Exception:
            pass

    def _on_message(self, event_type, data):
        if event_type == "sms":
            phone = data.get("phone", "")
            message = data.get("message", "")
            now = datetime.now().strftime("%H:%M")
            msg = {"direction": "received", "message": message, "time": now, "phone": phone}
            matched = None
            for c in self._clients:
                if c.identifier_for("sms").lstrip("+") == phone.lstrip("+"):
                    matched = c
                    break
            if matched:
                cid = matched.id
                if cid not in self._chat_messages:
                    self._chat_messages[cid] = []
                self._chat_messages[cid].append(msg)
                self.after(0, lambda n=matched.masked_identity, m=message[:80]: self._show_toast(f"SMS from {n}", m))
                if self._selected_client and self._selected_client.id == cid:
                    self.after(0, self._render_chat)
                self.after(0, self._render_contacts)

    def _update_status(self):
        if hasattr(self, 'sidebar_status'):
            color = "#4CAF50" if self._is_connected() else "#f44336"
            text = "Connected" if self._is_connected() else "Disconnected"
            self.sidebar_status.configure(text=f"  {text}", text_color=color)


class PhoneGateway:
    def __init__(self):
        self.base_url = ""
        self.connected = False
        self._poll_thread = None
        self._running = False
        self._callback = None

    def connect(self, url: str) -> bool:
        self.base_url = url.rstrip("/")
        try:
            req = urllib.request.Request(f"{self.base_url}/status")
            resp = urllib.request.urlopen(req, timeout=5)
            json.loads(resp.read())
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False

    def send_sms(self, phone: str, message: str) -> bool:
        try:
            data = json.dumps({"phone": phone, "message": message}).encode()
            req = urllib.request.Request(f"{self.base_url}/sms/send", data=data,
                                       headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read()).get("status") == "sent"
        except Exception:
            return False

    def make_call(self, phone: str) -> bool:
        try:
            data = json.dumps({"phone": phone}).encode()
            req = urllib.request.Request(f"{self.base_url}/call/make", data=data,
                                       headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception:
            return False

    def end_call(self) -> bool:
        try:
            data = json.dumps({}).encode()
            req = urllib.request.Request(f"{self.base_url}/call/end", data=data,
                                       headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False

    def get_inbox(self) -> list:
        try:
            req = urllib.request.Request(f"{self.base_url}/sms/inbox")
            resp = urllib.request.urlopen(req, timeout=5)
            return json.loads(resp.read()).get("messages", [])
        except Exception:
            return []

    def start_polling(self, callback):
        self._callback = callback
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self):
        self._running = False
        self.connected = False

    def _poll_loop(self):
        last = 0
        while self._running:
            try:
                inbox = self.get_inbox()
                if len(inbox) > last:
                    for msg in inbox[last:]:
                        if self._callback:
                            self._callback("sms", msg)
                    last = len(inbox)
            except Exception:
                pass
            time.sleep(3)


if __name__ == "__main__":
    app = SMSApp()
    app.mainloop()
