alter table public.jarvis_contacts
  add column if not exists archived_at timestamptz;

create index if not exists jarvis_contacts_active_idx
  on public.jarvis_contacts (owner_id, display_name)
  where archived_at is null;

create index if not exists jarvis_agenda_schedule_idx
  on public.jarvis_agenda_items (scheduled_for asc nulls last, created_at desc)
  where status = 'pending';

comment on column public.jarvis_contacts.archived_at is
  'Soft-delete marker; archived aliases stop resolving but remain recoverable server-side.';
