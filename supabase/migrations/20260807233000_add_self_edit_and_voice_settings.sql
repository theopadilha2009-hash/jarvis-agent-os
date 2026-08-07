alter table public.jarvis_device_commands
  drop constraint if exists jarvis_device_commands_action_check;

alter table public.jarvis_device_commands
  add constraint jarvis_device_commands_action_check
  check (action in (
    'open_application',
    'close_application',
    'message_send',
    'screen_capture',
    'storage_scan',
    'system_memory',
    'self_edit'
  ));

create table if not exists public.jarvis_settings (
  owner_id text not null default 'theo' check (owner_id = 'theo'),
  key text not null check (key ~ '^[a-z][a-z0-9_]{1,79}$'),
  value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default timezone('utc', now()),
  primary key (owner_id, key)
);

alter table public.jarvis_settings enable row level security;
revoke all on table public.jarvis_settings from anon, authenticated;

comment on column public.jarvis_device_commands.action is
  'Allowlisted local action; self_edit runs only in an isolated worktree and never retries after a stale claim.';
comment on table public.jarvis_settings is
  'Private single-operator runtime settings, including the active ElevenLabs voice identifier.';
