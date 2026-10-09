---
wizard: 0.2
id: secret-drop
name: Secret Drop
type: service
version: 0.1.1
summary: One-time encrypted links for handing an API key or password to an AI agent without chat.
license: MIT
source: https://github.com/mistermizel/secret-drop
runtime:
  kind: runtipi
  config: runtipi/config.json
  compose: runtipi/docker-compose.yml
skill: SKILL.md
provides: [secrets]
health: /health
---

# Secret Drop

One-time encrypted links for handing an API key or password to an AI agent without chat.
