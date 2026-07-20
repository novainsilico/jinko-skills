---
name: jk-sdk-setup
description: Authenticate and configure access to a Jinkō project via the jinko-sdk. Use this skill whenever the user wants to connect to Jinkō, install the SDK, set up credentials or a .env file, verify API access, fail-fast check that a JINKO_API_KEY and JINKO_PROJECT_ID work, or debug ConfigurationError, AuthenticationError, or AuthorizationError from the SDK. Do not use this skill for creating models, vpops, protocols, output sets, or trials.
compatibility: Requires Python 3.11+, the jinko Python SDK, JINKO_API_KEY, and JINKO_PROJECT_ID. Optional python-dotenv is recommended for local .env loading.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.2,<2.0"
license: MIT
---

# Jinkō SDK Setup

Use this skill for SDK setup and credential checks only. Keep the user focused on proving that Python can authenticate against Jinkō and read one project item list before moving to model, vpop, protocol, output-set, or trial workflows.

BE CAREFUL: the right package is `jinko-sdk` that export a `jinko` module. `jinko` is a different package unrelated to the Jinko SDK.

## Workflow

1. Confirm the user has Python 3.11+.
2. Install the Jinko SDK: `jinko-sdk`. 
3. Install  dotenv support when needed.
4. Ask the user to create an API key using `https://doc.jinko.ai/docs/api/` if they do not already have one.
5. Ask the user to set `JINKO_API_KEY` and `JINKO_PROJECT_ID` in their shell or local `.env` file.
6. Point them to `assets/.env.example` as the safe template. Do not ask them to paste secrets into chat.
6. Run or adapt `scripts/check_jinko_connection.py` to fail fast on configuration, authentication, authorization, or project-read-access issues.
7. If the check passes, report that the Jinkō connection is OK.
8. When the user wants to browse the project after setup, recommend `client.search(...)` as the default read-only exploration call before moving to a workflow-specific skill.

## Required Configuration

- `JINKO_API_KEY`: API key created in the Jinkō web interface.
- `JINKO_PROJECT_ID`: project identifier used by the SDK.

The SDK also supports `JINKO_BASE_URL`, but do not introduce alternate environments unless the user explicitly needs them.

## Validation Script

Use the bundled script instead of writing ad hoc checks:

```bash
python skills/jk-sdk-setup/scripts/check_jinko_connection.py
```

The script:

- Loads `.env` when `python-dotenv` is installed.
- Redacts sensitive values when showing configuration.
- Requires both `JINKO_API_KEY` and `JINKO_PROJECT_ID`.
- Constructs `JinkoClient()` from environment variables.
- Calls `client.auth_check()` to prove authentication and project read access.
- Prints minimal output on success.

Use `--show-config` only when debugging local setup; it prints presence and redacted values, never the full API key.

## After Validation

Once the connection check passes, prefer `client.search(...)` for project exploration because it gives the user an immediate view across project items.

Use a minimal example like:

```python
from jinko import JinkoClient

client = JinkoClient()
client.search(limit=20, columns="compact")
```

Use `search()` when the user wants to:

- browse what exists in the configured project
- find an item by name or free text
- orient themselves before choosing a model, protocol, vpop, or trial workflow

Keep the setup script focused on authentication and access checks. Use `search()` only after validation succeeds, not as a replacement for the fail-fast check.

## Troubleshooting

- For `ConfigurationError`, check that `.env` or the shell environment contains both required variables.
- For missing `JINKO_API_KEY`, direct the user to `https://doc.jinko.ai/docs/api/`.
- For `AuthenticationError`, assume the API key is missing, expired, malformed, or copied incorrectly.
- For `AuthorizationError`, assume the API key is valid but does not have access to the requested project.
- For other SDK request failures, check that `JINKO_PROJECT_ID` is copied exactly and that the network can reach Jink
- If the user uses `direnv`, ask them to ensure `.envrc` loads `.env`, then run `direnv allow`.
