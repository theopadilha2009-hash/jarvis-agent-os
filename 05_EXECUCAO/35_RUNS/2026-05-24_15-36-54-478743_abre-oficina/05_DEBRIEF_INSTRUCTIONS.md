# Debrief

```
cat > /tmp/jarvis-claude-out.md   # cole o RELATÓRIO FINAL e Ctrl+D
./jarvis project-memory-update --project oficina --from-file /tmp/claude-out.md --dry-run
./jarvis project-memory-update --project oficina --from-file /tmp/claude-out.md --apply
./jarvis self-cockpit
env JARVIS_NO_REPORT=1 ./jarvis safety-gate
env JARVIS_NO_REPORT=1 ./jarvis smoke-test
./jarvis doctrine-check
```
