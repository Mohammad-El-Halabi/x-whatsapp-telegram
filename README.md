# Staff Communications Control

This repository preserves the supplied projects and adds a unified Windows application with three simultaneous Telegram accounts and three simultaneous WhatsApp accounts. The supplied Signal and SMS clients remain available as separate Windows applications and use the same admin panel and Supabase allow-list.

## What is included

- `unified-app` — two tabs: three Telegram panels and three WhatsApp panels, side by side.
- `received/admin-panel` — owner administration for users, offices, account assignments, and approved contacts.
- `received/telegram-client` — the authoritative Telegram/Telethon source extracted from the supplied `assets.zip`.
- `received/whatsapp-app` — the supplied React, Tauri, and Node WhatsApp layers.
- `received/signal-client` — the supplied Signal client, restored to the shared Supabase configuration and packaged with `signal-cli`.
- `received/sms-client` — the supplied SMS client for an Android Termux gateway or a compatible USB modem.
- `received/admin-panel/supabase/migrations` — the complete database schema and security policies.

The similarly named ZIP files are not duplicates: the React frontend, Tauri backend, Node sidecar, Telegram source, Signal source, and SMS source are distinct layers. `assets.zip` remains preserved locally but is excluded from Git because it contains a live Telegram session, private downloaded media, and a plaintext environment file. Safe source was extracted to `received/telegram-client`; sessions, caches, build output, and secrets are ignored.

## Required behavior

- Telegram and WhatsApp each show exactly three independent panels without tab switching between accounts.
- Telegram slot 1 and WhatsApp slot 1 represent the same phone/account owner; the same pairing applies to slots 2 and 3. Each platform still has its own QR/device-link session.
- Switching the Telegram/WhatsApp tab does not disconnect the other platform.
- Contact lists and chats render the owner-defined `masked_identity`, never a client phone number or routing identifier.
- Only contacts enabled in Supabase for the selected platform and account gateway are accepted.
- Signal and SMS are standalone supplied applications. They are configured in the same admin panel and only load contacts enabled for their platform.
- Staff applications use only the Supabase public anon key. The service-role key belongs only in the owner admin panel.

## Supabase setup

For a new project, apply all migrations in filename order:

1. `000_initial_schema.sql`
2. `001_multi_account_support.sql`
3. `002_paired_account_slots.sql`
4. `003_restore_signal_sms.sql`

They can be run in the Supabase SQL Editor or from a linked Supabase CLI project. This repository's configured development project already has all four migrations applied; a client-owned replacement project must apply them again and use its own keys.

The admin panel then configures the live data:

1. Create offices and staff users in **Users**.
2. In **Assignments**, create Telegram + WhatsApp pairs for slots 1, 2, and 3. One action writes both rows with the same phone and gateway.
3. Add standalone Signal and/or SMS assignments only if those supplied clients are required.
4. In **Clients**, enter a staff-visible masked name, choose approved platforms, and enter the private platform routing identifiers.
5. Set `gateway_number` to an assignment's gateway key, or `default` to approve the contact for every account on the selected platform.

Supabase is the trusted source for authentication, office membership, account assignments, and the allow-list. Do not commit `.env` files, distribute the admin service-role key to staff, or put that key in any desktop application.

## Run the admin panel

```powershell
cd received\admin-panel
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Fill SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, and SECRET_KEY.
.venv\Scripts\python.exe run.py
```

Open `http://localhost:5001`. Production deployment instructions are in `received/admin-panel/SETUP.md`.

## Run the unified Telegram/WhatsApp application

Requirements: Node.js 20+, Python 3.11+, Rust, and the Windows Tauri prerequisites.

```powershell
cd unified-app
Copy-Item .env.example .env
# Fill the public Supabase values and Telegram API credentials.
npm.cmd ci --ignore-scripts --no-audit --no-fund
Push-Location sidecar
npm.cmd ci --ignore-scripts --no-audit --no-fund
Pop-Location
Push-Location telegram-sidecar
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location
npm.cmd run tauri:dev
```

Run `unified-app\build-windows.bat` to produce MSI and NSIS installers. On first use, scan each of the three Telegram QR codes from **Telegram Settings → Devices** and each of the three WhatsApp QR codes from **Linked devices**.

## Signal and SMS

Signal and SMS do not appear as extra tabs in the unified application; they are the separate supplied clients:

- Signal: see `received/signal-client/README.md`. It uses the unofficial open-source `signal-cli`, a local Java runtime, and a Signal link/registration step.
- SMS: see `received/sms-client/README.md`. Real SMS requires either an Android phone running the supplied Termux gateway or a compatible AT-command modem and SIM.

Software tests can validate authentication, allow-list behavior, builds, and startup. Actual Telegram, WhatsApp, Signal, and SMS delivery requires the client's real accounts, QR/device approval, phone/SIM, and network access.

## Build output

Builds are intentionally ignored because they are generated and may contain local configuration. Expected local outputs are:

- `received/admin-panel/dist/AdminPanel.exe`
- `received/signal-client/dist/Signal Staff Control.exe`
- `received/sms-client/dist/SMSStaffControl.exe`
- `unified-app/src-tauri/target/release/bundle/msi/*.msi`
- `unified-app/src-tauri/target/release/bundle/nsis/*-setup.exe`

GitHub Actions recompiles Python sources, applies the database migrations to a clean PostgreSQL instance, builds the web frontend and Telegram sidecar, and checks the Rust backend.
