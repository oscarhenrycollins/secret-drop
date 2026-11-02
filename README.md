# Secret Drop

One-time encrypted links for handing an API key or password to an AI agent without chat.

A [Wizard app](https://www.aiwizards.com/wizard-apps): install it from the Wizard Apps screen, or with the Wizard App Manager on any box running stock [Runtipi](https://runtipi.io).

- `wizard.md`: what the app is and what it gives the agent (spec: wizard.md v0.2).
- `runtipi/`: stock Runtipi `config.json` and `docker-compose.yml`.
- `mcp/`: the app's MCP front (`front.py` + `tools.py`), inlined into the compose file by `python3 mcp/inline.py`. It serves `/mcp` and passes everything else unchanged to the upstream container.
- `SKILL.md`: the skill the agent loads when this app is installed.
- Browser boundary (draft, default-off, wizard-os #133): with `WIZARD_BROWSER_BOUNDARY=1` the MCP front refuses every browser request and preflight on the agent side (`/mcp`, `/api/v1/requests…`). The recipient page keeps its own port (its own origin, never the owner's), its one-use link and its no-framing headers.
- `.github/workflows/publish.yml`: every push to `main` re-publishes to the index at apps.aiwizards.com.

Image build notes: [IMAGE.md](IMAGE.md).
