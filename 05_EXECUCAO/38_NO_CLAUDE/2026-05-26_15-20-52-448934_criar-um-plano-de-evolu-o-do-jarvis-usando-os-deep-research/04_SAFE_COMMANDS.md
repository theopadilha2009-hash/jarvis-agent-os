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
./jarvis plan "criar um plano de evolução do JARVIS usando os deep research adicionados, focando em n8n, agentes, subworkflows, memoria, logs e modo sem Claude" --save
./jarvis ask "criar um plano de evolução do JARVIS usando os deep research adicionados, focando em n8n, agentes, subworkflows, memoria, logs e modo sem Claude"
```

## Inspeção do projeto (read-only)
```
./jarvis project-intel --project jarvis-core
./jarvis project-memory --project jarvis-core
./jarvis project-cockpit --project jarvis-core
./jarvis project-open --project jarvis-core --print-only
```

## Blueprint local (research)
```
./jarvis blueprint --type research --goal "criar um plano de evolução do JARVIS usando os deep research adicionados, focando em n8n, agentes, subworkflows, memoria, logs e modo sem Claude"
```

## Gates (rodam local)
```
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
./jarvis command-audit
./jarvis doctrine-check
```
