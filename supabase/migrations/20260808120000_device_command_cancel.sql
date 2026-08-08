alter table public.jarvis_device_commands
  drop constraint if exists jarvis_device_commands_status_check;

alter table public.jarvis_device_commands
  add constraint jarvis_device_commands_status_check
  check (status in ('pending', 'running', 'succeeded', 'failed', 'canceled'));

comment on column public.jarvis_device_commands.status is
  'Lifecycle state. canceled is only written while a command is still pending.';
