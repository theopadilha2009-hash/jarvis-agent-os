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
./jarvis plan "preparar identidade pessoal do JARVIS com modos personal, work assist e future company" --save
./jarvis ask "preparar identidade pessoal do JARVIS com modos personal, work assist e future company"
```

## Inspeção do projeto (read-only)
```
./jarvis project-intel --project jarvis-core
./jarvis project-memory --project jarvis-core
./jarvis project-cockpit --project jarvis-core
./jarvis project-open --project jarvis-core --print-only
```

## Gates (rodam local)
```
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
./jarvis command-audit
./jarvis doctrine-check
```
