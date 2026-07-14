-- Multi-account Telegram and WhatsApp support.
-- Safe to run more than once in the Supabase SQL editor.

alter table public.staff_assignments
    add column if not exists platform text,
    add column if not exists gateway_number text default 'default',
    add column if not exists display_name text,
    add column if not exists connection_status text default 'disconnected',
    add column if not exists connection_data jsonb;

alter table public.clients_secure
    add column if not exists platforms text[] default '{}'::text[],
    add column if not exists platform_identifiers jsonb default '{}'::jsonb,
    add column if not exists gateway_number text default 'default';

create index if not exists staff_assignments_user_platform_idx
    on public.staff_assignments (user_id, platform, is_active);

create index if not exists clients_secure_office_gateway_idx
    on public.clients_secure (office_id, gateway_number);

comment on column public.staff_assignments.gateway_number is
    'Stable account key used to associate an approved client with one account slot.';

comment on column public.clients_secure.platform_identifiers is
    'Per-platform routing identifiers. These values must never be rendered in the staff UI.';
