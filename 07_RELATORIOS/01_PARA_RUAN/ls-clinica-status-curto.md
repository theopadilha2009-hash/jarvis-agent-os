# Mensagem curta para Ruan — LS Clínica

Ruan, conseguimos fazer a LS responder automaticamente no WhatsApp em teste controlado. Passei pela UAZAPI, n8n e IA usando o prompt da Dra. Larissa. A parte crítica foi corrigir a separação entre webhook de entrada e endpoint de envio `/send/text`, normalizar o payload real da UAZAPI e impedir loop com `fromMe` / `track_source`. Ainda não estou tratando como produção plena; o próximo passo seguro é validar mais casos e decidir a liberação controlada da instância.
