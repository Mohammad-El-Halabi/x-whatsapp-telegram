# Signal Staff Control

This is the separate Signal client supplied with the project. It authenticates staff through Supabase, validates the staff member's Signal assignment, and replaces the Signal address book with contacts explicitly enabled for `signal` in the owner's allow-list.

## Prepare and run from source

```powershell
cd received\signal-client
Copy-Item .env.example .env
# Fill SUPABASE_URL and SUPABASE_ANON_KEY only.
powershell -ExecutionPolicy Bypass -File .\prepare-runtime.ps1
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

`prepare-runtime.ps1` downloads the pinned `signal-cli` release and a local Java runtime, then verifies the command. `signal-cli` is an unofficial Signal command-line client and must be kept current when Signal changes its service protocol.

## Build and distribute

Run `build.bat`. Place these beside `dist\Signal Staff Control.exe`:

- `.env` containing the project URL and anon key
- `signal-cli-wrapper.bat`
- `signal-cli\`
- `runtime\java\`

The service-role key must never be included. A real Signal account must still be linked or registered by its owner.
