You are working inside the JARVIS local project.

Goal for this weekend:
Use Claude Code to improve JARVIS safely and professionally, without losing the current project structure.

Current status:
- v0.6 run-safe is closed.
- release-check passed.
- safety-gate passed.
- quality-gate passed.
- Git was clean.
- Production was not changed.

Your first task is READ-ONLY AUDIT.
Do not edit files yet.

Start with:
1. git status --short
2. git branch --show-current
3. git log --oneline -10
4. inspect the command structure enough to understand:
   - run-safe
   - local-exec-session
   - local-exec-review
   - command-audit
   - release-check
   - safety-gate
   - quality-gate

Return:
1. diagnosis of current JARVIS architecture
2. what v0.6 already solves
3. top 5 improvements for v0.7
4. which improvement should be implemented first
5. files likely involved
6. risks
7. exact validation commands
8. whether you recommend using /goal or not for this repo

Rules:
- Do not edit files.
- Do not read .env or secrets.
- Do not touch VPS, n8n, production, deploy, push, or PR.
- Do not generate PDFs.
- Do not create random sources.
- Keep response practical and concise.
