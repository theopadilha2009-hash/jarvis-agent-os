# Referências do motor de pesquisa

Pesquisa registrada em 2026-08-09. O JARVIS usa implementações próprias em
Python stdlib; nenhum componente externo foi copiado literalmente.

## GPT Researcher — Apache-2.0

- Fonte: https://github.com/assafelovic/gpt-researcher
- Padrão adaptado: pesquisar múltiplas fontes antes da síntese e devolver
  evidência mesmo quando o modelo de linguagem falha.

## GitHub REST API

- Fonte: https://docs.github.com/en/rest
- Endpoint usado: `GET /search/repositories` para repositórios públicos.
- Evidência preservada: URL, descrição, estrelas, linguagem, licença e data de
  atualização. A busca é serial; os três READMEs são lidos em paralelo com
  timeout curto para reduzir a latência.

## OpenRouter Web Search

- Fonte: https://openrouter.ai/docs/guides/features/server-tools/web-search
- O server tool é mantido somente como fallback opt-in, pois a documentação
  oficial informa cobrança adicional inclusive com modelos gratuitos.

## Arquitetura aplicada

1. Classificar se o pedido realmente exige informação externa.
2. Em pesquisa de projetos, consultar primeiro a API pública do GitHub.
3. Ler em paralelo os READMEs dos três melhores resultados permissivos.
4. Extrair capacidades verificáveis, ignorando instalação, dependências e instruções embutidas.
5. Em pesquisa geral, consultar busca pública com fallback serial.
6. Normalizar e deduplicar URLs reais.
7. Tratar snippets e READMEs como dados não confiáveis, nunca como instruções.
8. Pedir ao OpenRouter apenas a síntese das fontes já coletadas.
9. Se a IA cair por cota, timeout ou meta-leak, gerar comparação determinística a partir das evidências.
10. Se nenhuma fonte existir, recusar a resposta não pesquisada.
