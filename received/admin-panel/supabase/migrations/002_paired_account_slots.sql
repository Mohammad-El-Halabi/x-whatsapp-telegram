-- Explicitly pair Telegram N with WhatsApp N for slots 1, 2, and 3.
-- Safe to run after 001 and safe to run more than once.

alter table public.staff_assignments
    add column if not exists account_slot smallint;

-- Backfill only unambiguous legacy pairs: exactly one Telegram row and one
-- WhatsApp row already sharing the same staff member, phone, and gateway.
with paired_groups as (
    select user_id,
           phone_number,
           gateway_number,
           min(created_at) as first_created
    from public.staff_assignments
    where account_slot is null
      and lower(platform) in ('telegram', 'whatsapp')
    group by user_id, phone_number, gateway_number
    having count(*) filter (where lower(platform) = 'telegram') = 1
       and count(*) filter (where lower(platform) = 'whatsapp') = 1
), ranked as (
    select *,
           row_number() over (
               partition by user_id
               order by first_created nulls last, phone_number, gateway_number
           ) as slot_number
    from paired_groups
)
update public.staff_assignments as assignment
set account_slot = ranked.slot_number
from ranked
where assignment.user_id = ranked.user_id
  and assignment.phone_number = ranked.phone_number
  and assignment.gateway_number = ranked.gateway_number
  and assignment.account_slot is null
  and ranked.slot_number between 1 and 3;

alter table public.staff_assignments
    drop constraint if exists staff_assignments_account_slot_check,
    add constraint staff_assignments_account_slot_check
        check (account_slot is null or account_slot between 1 and 3);

create unique index if not exists staff_assignments_user_platform_slot_unique
    on public.staff_assignments (user_id, platform, account_slot)
    where account_slot is not null;

comment on column public.staff_assignments.account_slot is
    'Shared slot number (1-3). Telegram and WhatsApp rows in the same slot represent the same phone/account owner.';

create or replace function public.enforce_staff_assignment_pair_consistency()
returns trigger
language plpgsql
as $$
declare
    pair_user uuid;
    pair_slot smallint;
    pair_count integer;
    telegram_count integer;
    whatsapp_count integer;
    phone_count integer;
    gateway_count integer;
begin
    if tg_op = 'DELETE' then
        pair_user := old.user_id;
        pair_slot := old.account_slot;
    else
        pair_user := new.user_id;
        pair_slot := new.account_slot;
    end if;

    if pair_slot is null then
        if tg_op = 'DELETE' then return old; else return new; end if;
    end if;

    select count(*),
           count(*) filter (where lower(platform) = 'telegram'),
           count(*) filter (where lower(platform) = 'whatsapp'),
           count(distinct phone_number),
           count(distinct gateway_number)
    into pair_count, telegram_count, whatsapp_count, phone_count, gateway_count
    from public.staff_assignments
    where user_id = pair_user and account_slot = pair_slot;

    if pair_count not in (0, 2)
       or (pair_count = 2 and (telegram_count <> 1 or whatsapp_count <> 1 or phone_count <> 1 or gateway_count <> 1)) then
        raise exception 'Account slot % must contain one Telegram and one WhatsApp row with the same phone number and gateway', pair_slot;
    end if;
    if tg_op = 'DELETE' then return old; else return new; end if;
end;
$$;

drop trigger if exists staff_assignment_pair_consistency on public.staff_assignments;
create constraint trigger staff_assignment_pair_consistency
    after insert or update of user_id, platform, account_slot, phone_number, gateway_number or delete
    on public.staff_assignments
    deferrable initially deferred
    for each row
    execute function public.enforce_staff_assignment_pair_consistency();
