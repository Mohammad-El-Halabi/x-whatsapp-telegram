# Staff Communications Control

This repository preserves the supplied projects and adds one desktop application with three simultaneous Telegram accounts and three simultaneous WhatsApp accounts.

## Repository layout

- `received/admin-panel` — extracted Flask/Supabase owner administration panel, extended for platform and account selection.
- `received/telegram-client` — the missing authoritative Telegram/Telethon client extracted from `assets.zip`.
- `received/signal-client` — the previously supplied Signal source, preserved unchanged as a received project but not used by the unified application.
- `received/sms-client` — original SMS desktop client source.
- `received/whatsapp-app` — the original React, Tauri, and Node WhatsApp layers assembled correctly.
- `unified-app` — the new two-tab desktop application.

The similarly named original ZIP files are not duplicates: the React frontend, Tauri backend, and Node sidecar are separate required layers. `assets.zip` is also distinct. It remains preserved locally but is intentionally excluded from Git because it contains a live Telegram session, downloaded private media, and a plaintext environment file. Its safe source is extracted under `received/telegram-client`; runtime sessions, media, caches, and secrets are excluded.

## Resulting behavior

- The Telegram tab displays exactly three independent account panels side by side.
- The WhatsApp tab displays exactly three independent account panels side by side.
- Switching tabs does not disconnect or pause the other platform.
- Every slot has an independent persisted Telegram or WhatsApp session and its own QR linking flow.
- Telegram uses the supplied Telethon architecture through a bundled local sidecar.
- Staff receive only opaque client IDs and masked names in the webview. Real Telegram IDs and WhatsApp routing identifiers remain behind the Rust boundary.
- Incoming chats and messages from contacts not approved in Supabase are discarded before reaching the UI.
- Outgoing commands accept only a Supabase client ID and are rejected unless that client is approved for that platform and account.

## Owner configuration

1. Run `received/admin-panel/supabase/migrations/001_multi_account_support.sql` in the Supabase SQL editor.
2. Create three active `telegram` assignments and three active `whatsapp` assignments for each staff member.
3. Give each assignment a unique gateway key and a staff-safe display name. The first three active assignments, ordered by creation time, become slots 1–3.
4. Add clients in **Clients**, select Telegram, WhatsApp, or both, and enter the corresponding Telegram numeric user ID and/or WhatsApp identifier.
5. Set the client's gateway to the specific assignment key. `default` approves that client for all three accounts on each selected platform.
6. Use `masked_identity` as the staff-visible name. Actual identifiers remain visible only in the owner admin panel.

## Unified application setup

Requirements:

- Node.js 20+ and npm.
- Python 3.11+ to build the bundled Telethon sidecar.
- Rust and the Windows Tauri prerequisites.
- Chrome or Edge for the WhatsApp Web runtime.

Copy `unified-app/.env.example` to `unified-app/.env`, then set the Supabase public configuration and Telegram API application credentials. Never put a Supabase service-role key in the staff application.

For development, install the frontend, WhatsApp, and Telegram dependencies, then run Tauri:

```powershell
cd unified-app
npm.cmd ci --ignore-scripts --no-audit --no-fund
cd sidecar
npm.cmd ci --ignore-scripts --no-audit --no-fund
cd ..\telegram-sidecar
python -m pip install -r requirements.txt
cd ..
npm.cmd run tauri:dev
```

`build-windows.bat` installs the safe dependency sets, creates the PyInstaller Telegram sidecar, and builds the Windows installer.

## Account linking

- Telegram: each unlinked slot displays its own QR code. In Telegram, open **Settings → Devices → Link Desktop Device** and scan it. If two-step verification is enabled, the local app requests the password without storing or sending it anywhere except the local Telethon runtime.
- WhatsApp: each unlinked slot displays its own QR code. Scan it with the corresponding account under **Linked devices**.

No client number or routing identifier is rendered in account headers, contact lists, chats, notifications, errors, or QR instructions.
