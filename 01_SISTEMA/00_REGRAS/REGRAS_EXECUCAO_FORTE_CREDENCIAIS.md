# Regras de Execução Forte — JARVIS Theo Padilha AI Worker

## Data
2026-05-21T14:33:45

## Decisão
O JARVIS deve evoluir para operar projetos reais, VPS, Docker, n8n, workflows, Git, deploys e integrações completas.

## Ponto importante
Credenciais, chaves, tokens e senhas podem ser usados localmente quando houver autorização e necessidade operacional.

## O que é proibido
- imprimir segredo no terminal sem necessidade;
- salvar segredo em Git;
- salvar segredo em relatório Markdown/TXT/PDF;
- enviar segredo para ChatGPT, Claude, Gemini ou outro executor externo;
- commitar `.env`, token, QR Code, cookie, service_role, chave SSH ou senha;
- exportar workflow n8n configurado com credencial real dentro do JSON;
- registrar headers Authorization, Bearer ou cookies em logs permanentes.

## O que é permitido
- usar credencial já configurada no n8n Credentials;
- usar `.env` local não commitado;
- usar variáveis de ambiente locais;
- usar prompt interativo com `read -s` no terminal;
- usar cofre externo como 1Password, Bitwarden, Infisical ou Keychain;
- operar VPS/Portainer/Docker/n8n quando o modo de execução permitir;
- criar workflows completos desde que secrets fiquem fora do JSON/Git/chat.

## Modos de permissão

### PREPARE
Planeja, cria briefing, handoff, prompts, checklist e relatórios. Não altera projeto real.

### READONLY
Inspeciona arquivos, Git, logs, Docker, n8n, VPS ou projeto sem alterar nada.

### LOCAL_EXEC
Pode editar projeto local, criar branch, rodar build/teste e preparar commit. Sem push/deploy sem autorização.

### INFRA_EXEC
Pode operar VPS, Docker, Portainer, Traefik, n8n e serviços reais, com escopo explícito e backup/checkpoint antes de ação sensível.

### PRODUCTION_ARMED
Modo para ação real sensível: deploy, push, merge, ativar workflow, enviar mensagem real, alterar banco real, trocar DNS, rodar migration ou mexer em credencial produtiva. Exige autorização explícita.

## Frase de status correta
JARVIS pode operar forte, mas precisa declarar o modo, o escopo, o que foi testado e se produção foi alterada.

## Regra final
Poder máximo não significa permissão solta. Significa execução forte com modo certo, logs certos, segredo protegido e status real.
