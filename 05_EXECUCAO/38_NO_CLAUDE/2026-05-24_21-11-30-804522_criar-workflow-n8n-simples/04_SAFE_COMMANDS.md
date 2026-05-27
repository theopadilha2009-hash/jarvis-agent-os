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
./jarvis plan "criar workflow n8n simples" --save
./jarvis ask "criar workflow n8n simples"
```

## Blueprint local (n8n)
```
./jarvis blueprint --type n8n --goal "criar workflow n8n simples"
```

## Gates (rodam local)
```
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
./jarvis command-audit
./jarvis doctrine-check
```
