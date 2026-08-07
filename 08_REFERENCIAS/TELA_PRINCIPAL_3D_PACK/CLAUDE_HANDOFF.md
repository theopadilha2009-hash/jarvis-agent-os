# CLAUDE_HANDOFF — Tela principal 3D / visuais JARVIS

**Onde está este pack:** `08_REFERENCIAS/TELA_PRINCIPAL_3D_PACK/`

**Pedido do Theo:** salvar os visuais da tela principal (Avatar/boneco, Core, Source, Forge)
para o Claude poder mexer e restaurar sem perder o que já existe.

## O que é cada modo (tabs no hero)

| Tab | O que é | Arquivo neste pack |
|-----|---------|--------------------|
| **Avatar** (default) | Boneco/cabeça 3D real (GLB) + material vidro/obsidiana | `models/01_avatar_boneco_humanoid.glb` + `engines/01_avatar_engine.js` |
| **Core** | Cristal AI procedural Three.js (sem GLB) | `engines/02_core_engine.js` |
| **Source** | Constelação canvas 2D de fontes | `engines/03_source_engine.js` |
| **Forge / Forja** | Scaffold + shards 2D (NÃO é o boneco) | `engines/04_forge_engine.js` |

## Runtime (onde o app carrega de verdade)

- Modelo ativo: `11_SCRIPTS/jarvis_ui_assets/models/jarvis-humanoid.glb`
- Alias/variante: `11_SCRIPTS/jarvis_ui_assets/models/variants/01_avatar_boneco_humanoid.glb` (mesmo hash)
- Cockpit monólito: `11_SCRIPTS/jarvis_ui_assets/cockpit.html`
- Web gateway: `web/jarvis-3d.js` (também carrega o mesmo GLB)
- Servido em: `/asset/models/jarvis-humanoid.glb` (via `api/index.py`)

## Snapshot completo

- `cockpit_snapshot/cockpit.html` — cópia inteira do cockpit no momento do pack
- `runtime_web/*` — UI web (index, css, js, 3d)

## Como trocar / restaurar o boneco 3D

1. Edite ou substitua o GLB em `models/` deste pack.
2. Copie para o runtime:
   ```bash
   cp 08_REFERENCIAS/TELA_PRINCIPAL_3D_PACK/models/01_avatar_boneco_humanoid.glb \
      11_SCRIPTS/jarvis_ui_assets/models/jarvis-humanoid.glb
   ```
3. Se mudar materiais/comportamento, porte o patch de `engines/01_avatar_engine.js`
   de volta para o bloco `makeAvatar()` em `cockpit.html` (e espelhe em `web/jarvis-3d.js` se a web for o alvo).

## Como mexer na Forja / Core / Source

Esses **não** têm arquivo `.glb`. Edite o engine correspondente e reintegre no
`cockpit.html` nas linhas indicadas no header de cada `engines/*.js`.

## Hash do GLB no pack (SHA-256)

`a30ae1e010efd9cf438d486591fc068d01e48a7b34eaf47616c7396abbc1513e`

## Inventário

Ver `MANIFEST.json` (paths, bytes, hashes).

## Não fazer

- Não apagar `jarvis-humanoid.glb` do runtime sem deixar um substituto com o mesmo path
  (health check e testes cobrem esse arquivo).
- Não confundir **Forge** (forja visual) com o **boneco 3D** (Avatar).
- Não commitar `.env` / tokens.

Produção: pack é só referência + cópias versionadas; deploy publica o runtime normalmente.
