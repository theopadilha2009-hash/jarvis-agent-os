# Model variants (runtime)

- `01_avatar_boneco_humanoid.glb` — boneco 3D da tela principal (Avatar)
- Runtime ativo: `../jarvis-humanoid.glb` (mesmo arquivo, hash idêntico)

Os modos **Core / Source / Forge** NÃO têm GLB próprio — são engines procedurais
em JS. Os fontes exportados estão em:
`08_REFERENCIAS/TELA_PRINCIPAL_3D_PACK/engines/`

Para trocar o boneco ativo: copie o GLB desejado sobre `../jarvis-humanoid.glb`
(ou altere a URL em cockpit.html / web/jarvis-3d.js).
