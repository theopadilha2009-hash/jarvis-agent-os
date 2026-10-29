-- Alinha o CHECK da fila do Mac com o que o gateway enfileira e o worker aceita.
--
-- Sintoma em produção: qualquer ação enfileirada voltava 400
--   'new row for relation "jarvis_device_commands" violates check constraint
--    "jarvis_device_commands_action_check"'
-- e o app respondia "O Supabase recusou a fila do Mac (HTTP 400)".
--
-- A produção estava com o CHECK da primeira migration (6 ações). As migrations
-- de 07/08 e 19/08 que ampliaram a lista nunca foram aplicadas lá.

alter table public.jarvis_device_commands
  drop constraint if exists jarvis_device_commands_action_check;

alter table public.jarvis_device_commands
  add constraint jarvis_device_commands_action_check
  check (action in (
    -- app do Mac (device_worker.ALLOWED_ACTIONS)
    'open_application',
    'close_application',
    'spotify_control',
    'message_send',
    'screen_capture',
    'screen_record',
    'github_overview',
    'storage_scan',
    'system_memory',
    'self_edit',
    'save_note',
    'reminder',
    'open_url',
    'clipboard_set',
    'speak',
    'open_folder',
    'notify',
    'volume_set',
    'image_convert',
    'files_triage',
    -- gateway (api/index.py): lembrete e foco entram na mesma fila
    'reminder_set',
    'focus_set'
  ));