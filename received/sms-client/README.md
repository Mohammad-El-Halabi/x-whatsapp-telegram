# SMS Staff Control

This is the separate SMS client supplied with the project. It authenticates staff through Supabase and only loads contacts explicitly enabled for `sms` in the owner's allow-list. Contact cards and search use masked names; routing numbers stay hidden in the UI.

## Run from source

```powershell
cd received\sms-client
Copy-Item .env.example .env
# Fill SUPABASE_URL and SUPABASE_ANON_KEY only.
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Run `build.bat` to create `dist\SMSStaffControl.exe`, then place the configured `.env` beside the executable. Never include a service-role key.

## Required SMS transport

The desktop program cannot send cellular SMS by itself. Use one of the supplied transports:

- Android gateway: copy `phone_server.py` to an Android phone with Termux and Termux:API installed, grant SMS/phone permissions, run the server, then connect the desktop client to the phone's local-network URL.
- USB modem: connect a compatible SIM modem that supports standard AT commands and configure `MODEM_PORT` and `MODEM_BAUD`.

Real delivery tests require the client's phone or modem, SIM, permissions, and network. Do not expose the Android gateway to the public internet; keep it on a trusted local network.
