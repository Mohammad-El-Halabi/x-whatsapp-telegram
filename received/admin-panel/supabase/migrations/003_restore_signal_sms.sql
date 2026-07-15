-- Restore the Signal and SMS platforms supplied with the original project.
-- Telegram/WhatsApp continue to use paired slots 1-3; Signal/SMS remain
-- standalone assignments with a null account_slot.

alter table public.users
    drop constraint if exists users_role_check,
    add constraint users_role_check
        check (role in ('staff', 'manager', 'admin', 'superadmin'));

alter table public.staff_assignments
    drop constraint if exists staff_assignments_platform_check,
    add constraint staff_assignments_platform_check
        check (lower(platform) in ('telegram', 'whatsapp', 'signal', 'sms')),
    drop constraint if exists staff_assignments_platform_slot_check,
    add constraint staff_assignments_platform_slot_check
        check (
            (lower(platform) in ('telegram', 'whatsapp') and account_slot between 1 and 3)
            or
            (lower(platform) in ('signal', 'sms') and account_slot is null)
        );

create unique index if not exists staff_assignments_user_standalone_platform_unique
    on public.staff_assignments (user_id, platform)
    where lower(platform) in ('signal', 'sms');

comment on column public.staff_assignments.platform is
    'Telegram and WhatsApp use paired account slots 1-3. Signal and SMS are standalone supplied clients.';
