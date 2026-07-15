-- Complete bootstrap for a new Supabase project.
-- Run this first in the Supabase SQL editor, then run 001, 002, and 003.

create extension if not exists pgcrypto;

create table if not exists public.offices (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    email text not null unique,
    password text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.users (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique,
    full_name text not null,
    role text not null default 'staff' check (role in ('staff', 'manager', 'admin', 'superadmin')),
    office_id uuid references public.offices(id) on delete set null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.staff_assignments (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    office_id uuid references public.offices(id) on delete set null,
    platform text not null check (lower(platform) in ('telegram', 'whatsapp', 'signal', 'sms')),
    phone_number text not null,
    gateway_number text not null default 'default',
    account_slot smallint check (account_slot is null or account_slot between 1 and 3),
    display_name text,
    is_active boolean not null default true,
    connection_status text not null default 'disconnected',
    connection_data jsonb,
    last_connected_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.clients_secure (
    id uuid primary key default gen_random_uuid(),
    masked_identity text not null,
    real_identifier text not null,
    office_id uuid references public.offices(id) on delete cascade,
    gateway_number text not null default 'default',
    platforms text[] not null default '{}'::text[],
    platform_identifiers jsonb not null default '{}'::jsonb,
    staff_id uuid references public.users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists staff_assignments_user_platform_slot_unique
    on public.staff_assignments (user_id, platform, account_slot)
    where account_slot is not null;

create index if not exists staff_assignments_user_platform_idx
    on public.staff_assignments (user_id, platform, is_active);

create index if not exists clients_secure_office_gateway_idx
    on public.clients_secure (office_id, gateway_number);

alter table public.users enable row level security;
alter table public.staff_assignments enable row level security;
alter table public.clients_secure enable row level security;

drop policy if exists users_read_self on public.users;
create policy users_read_self on public.users
    for select to authenticated
    using (id = auth.uid());

drop policy if exists assignments_read_self on public.staff_assignments;
create policy assignments_read_self on public.staff_assignments
    for select to authenticated
    using (user_id = auth.uid());

drop policy if exists assignments_update_self on public.staff_assignments;
create policy assignments_update_self on public.staff_assignments
    for update to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

drop policy if exists clients_read_own_office on public.clients_secure;
create policy clients_read_own_office on public.clients_secure
    for select to authenticated
    using (
        office_id in (
            select office_id from public.users where id = auth.uid() and is_active = true
        )
    );

revoke all on public.users, public.staff_assignments, public.clients_secure from anon;
grant select on public.users, public.staff_assignments, public.clients_secure to authenticated;
grant update (connection_status, connection_data, last_connected_at, updated_at)
    on public.staff_assignments to authenticated;

comment on table public.clients_secure is
    'Owner-managed allow-list. Raw routing identifiers must never be rendered in the staff webview.';
