# Staff Admin Panel — Setup Guide

## Requirements
- Python 3.10+
- Supabase project (URL + Anon Key + Service Role Key)

## Quick Setup

If no Supabase project exists, create one at `https://supabase.com`, open **SQL Editor**, and run these files in order:

1. `supabase/migrations/000_initial_schema.sql`
2. `supabase/migrations/001_multi_account_support.sql`
3. `supabase/migrations/002_paired_account_slots.sql`
4. `supabase/migrations/003_restore_signal_sms.sql`

The Supabase project is not optional in this architecture: it authenticates staff and stores the owner-controlled office, paired-account, and approved-contact rules. A project URL or API key does not grant Dashboard access; the project owner must send an invitation, or a new project must be created.

The same migrations can be applied from a terminal with PostgreSQL's `psql`. Set the database connection string supplied by the project owner, then run:

```powershell
$env:SUPABASE_DB_URL = 'postgresql://...'
Get-ChildItem .\supabase\migrations\*.sql | Sort-Object Name | ForEach-Object {
    psql $env:SUPABASE_DB_URL -v ON_ERROR_STOP=1 -f $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Migration failed: $($_.Name)" }
}
```

Do not place the database password or service-role key in Git.

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate it
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Then edit .env with your Supabase credentials

# 5. Run the app
python run.py
```

The app will be available at `http://localhost:5001`

## Environment Variables (.env)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | Supabase service_role key (for admin operations) |
| `SECRET_KEY` | Persistent random Flask session secret; generate a strong value for production |
| `FLASK_DEBUG` | Set to `1` for debug mode, `0` for production |
| `FLASK_HOST` | Bind address (default: `0.0.0.0`) |
| `FLASK_PORT` | Port (default: `5001`) |

## Production Deployment

For production, use a WSGI server:

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5001 wsgi:app
```

Or with Gunicorn (Linux/Mac):
```bash
pip install gunicorn
gunicorn -b 0.0.0.0:5001 wsgi:app
```

## Project Structure

```
admin-panel/
├── run.py              # Development server
├── wsgi.py             # Production WSGI entry point
├── requirements.txt
├── .env.example        # Environment template
├── SETUP.md            # This file
├── src/
│   ├── config/
│   │   └── settings.py
│   ├── models/
│   │   └── schemas.py
│   ├── routes/
│   │   └── admin.py
│   ├── services/
│   │   └── supabase_service.py
│   └── templates/      # HTML templates
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── users.html
│       ├── assignments.html
│       └── clients.html
```

## First Admin User

After setup, create the first admin user directly in your Supabase dashboard:
1. Go to **Authentication > Users** and create a user (set email + password)
2. Go to **SQL Editor** and run:
```sql
INSERT INTO public.users (id, email, full_name, role)
VALUES ('<USER_ID_FROM_AUTH>', 'admin@example.com', 'Admin', 'superadmin');
```

Or use the admin panel's **Add User** button after logging in as an existing admin.
