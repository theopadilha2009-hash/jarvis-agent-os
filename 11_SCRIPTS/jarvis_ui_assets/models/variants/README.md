# Model variants (runtime)

- `01_avatar_boneco_humanoid.glb` — busto humanoide frontal da tela principal.
- Runtime web ativo: este arquivo, servido em
  `/asset/models/variants/01_avatar_boneco_humanoid.glb`.
- `../jarvis-humanoid.glb` permanece como modelo legado compatível; ele não é o
  avatar padrão porque a animação embutida gira o busto e inclui um plano de
  partículas que atravessa a face.

Os modos **Core / Source / Forge** NÃO têm GLB próprio — são engines procedurais
em JS. Os fontes exportados estão em:
`08_REFERENCIAS/TELA_PRINCIPAL_3D_PACK/engines/`

Para trocar o boneco ativo, altere a URL versionada em `web/jarvis-3d.js` e
atualize o self-test do gateway em `api/index.py`.
