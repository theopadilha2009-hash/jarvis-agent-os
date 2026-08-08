# Third-party references

No third-party source file is vendored by the JARVIS web runtime. The project
adapts small architectural patterns from the references below and keeps its
own stdlib/vanilla-JavaScript implementation.

## AG-UI Protocol

- Project: [ag-ui-protocol/ag-ui](https://github.com/ag-ui-protocol/ag-ui)
- License: MIT
- Use here: lifecycle event vocabulary for `jarvis-events/1` (`RUN_STARTED`,
  tool-call events and terminal run events).

The original project and its license remain the property of their respective
authors and contributors.

## assistant-ui and CopilotKit

- Projects: [assistant-ui/assistant-ui](https://github.com/assistant-ui/assistant-ui)
  and [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit)
- License: MIT (both projects)
- Use here: inspiration for typed, generative result cards rendered from real
  backend state rather than parsing arbitrary model prose.

## Leon and Mem0

- Projects: [leon-ai/leon](https://github.com/leon-ai/leon) (MIT) and
  [mem0ai/mem0](https://github.com/mem0ai/mem0) (Apache-2.0)
- Use here: inspiration for layered owner/project/daily/discussion memory and
  relevance-first retrieval. JARVIS keeps its existing private Supabase table
  and does not vendor either project's runtime.
