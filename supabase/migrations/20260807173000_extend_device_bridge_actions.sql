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
    'system_memory'
  ));

comment on column public.jarvis_device_commands.action is
  'Allowlisted local action; arbitrary shell and arbitrary paths are rejected by DB and worker.';
