# Comandos seguros (você executa)

## Diagnóstico
```
./jarvis doctor-agent
./jarvis state-status
./jarvis limits
./jarvis resume
```

## Planejamento local (sem Claude)
```
./jarvis plan "workflow n8n para agendamento de WhatsApp Business" --save
./jarvis ask "workflow n8n para agendamento de WhatsApp Business"
```

## Blueprint local (n8n)
```
./jarvis blueprint --type n8n --goal "workflow n8n para agendamento de WhatsApp Business"
```

## Gates (rodam local)
```
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
./jarvis command-audit
./jarvis doctrine-check
```
