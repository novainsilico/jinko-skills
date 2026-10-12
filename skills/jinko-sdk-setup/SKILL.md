---
name: jinko-sdk-setup
description: Authenticate and configure access to a Jinkō project via the jinko-sdk. Use this skill whenever the user wants to connect to Jinkō, install the SDK, set up credentials or a .env file, verify API access, fail-fast check that a JINKO_API_KEY or JINKO_SESSION_CODE and JINKO_PROJECT_ID work, obtain a session code from the Jinko MCP get_session_code tool, tell a project key from an organization key, choose between JinkoClient and JinkoOrgClient, or debug ConfigurationError, AuthenticationError, or AuthorizationError from the SDK. Do not use this skill for creating models, vpops, protocols, output sets, or trials.
compatibility: Requires Python 3.11+ and network access. The validation script diagnoses missing or outdated SDK installations, credentials, and optional python-dotenv support.
metadata:
  author: Nova In Silico
  requires_sdk: ">=1.14,<2.0"
license: MIT
---

# Jinkō SDK Setup

Use this skill for SDK setup and credential checks only. Keep the user focused on proving that Python can authenticate against Jinkō and read one project item list before moving to model, vpop, protocol, output-set, or trial workflows.

BE CAREFUL: the right package is `jinko-sdk` that export a `jinko` module. `jinko` is a different package unrelated to the Jinko SDK.

## Credentials

Do this before the connection check. A missing `.env` is expected when a Jinko MCP server is connected. Do not stop to create one.

`JinkoClient()` reads credentials from the environment. Export both of these for every SDK command:

1. `JINKO_PROJECT_ID` — the id of the project the user is working in. Always set this. Do not invent one.
2. One credential. Prefer `JINKO_SESSION_CODE` when the Jinko MCP tool `get_session_code` is available. Use `JINKO_API_KEY` only when that tool is not available. When both are set, `JINKO_SESSION_CODE` is the one to use.

### Session code

A session code can be exchanged only once. Call `get_session_code` immediately before each SDK process, including the connection check and every later command. Do not reuse a code that was already passed to a process.

1. Call `get_session_code` with no arguments.
2. The tool returns JSON with `code` and `expiresAt`. Export `code` as `JINKO_SESSION_CODE` for that one process.
3. Keep the code out of `.env`, chat, logs, and version control.
4. Inside that process the SDK exchanges the code once, keeps the bearer in `JINKO_API_TOKEN`, and drops `JINKO_SESSION_CODE`. A new process does not see that bearer. Fetch a new code for it.
5. Also call `get_session_code` again after `expiresAt`, or when the SDK reports an authentication failure.

If `get_session_code` fails and `JINKO_API_KEY` is already configured, continue with the API key and say that the session code was unavailable.

### API key

Use `JINKO_API_KEY` from the environment or a local `.env` only when no Jinko MCP `get_session_code` tool is available. Do not ask the user to paste the key into chat.

## Workflow

> **SDK VERSION PREREQUISITE:** Run the check below. It ships with the SDK and
> verifies the installed SDK against every neighboring SDK-dependent skill
> before API access.

Run the deterministic check and follow its success or error message:

```bash
python -m jinko.cli.check_jinko_connection
```

The script:

- Loads `.env` when `python-dotenv` is installed.
- Redacts sensitive values when showing configuration.
- Requires `JINKO_API_KEY`, which holds either a project key or an organization key or `JINKO_SESSION_CODE`. When both credential variables are set, `JINKO_SESSION_CODE` is used.
- Without `JINKO_PROJECT_ID`, lists the projects visible to the key with `JinkoOrgClient().list_projects()`. This list does not show the key scope, so the script does not report the key type.
- With `JINKO_PROJECT_ID`, constructs `JinkoClient()`, calls `client.auth_check()`, then `client.search(limit=1, show_table=False, show_table_hint=False)` to prove minimal read-only project-item access.
- Prints minimal output on success, including the key type when `JINKO_PROJECT_ID` is set.

Use `--show-config` only when debugging local setup; it prints presence and redacted values, never the full API key or session code.

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

The setup script uses a one-item, non-rendered `search()` only as its project-read check after authentication. Use a larger interactive `search()` only for exploration after validation succeeds.

## Reading SDK signatures

Import only `JinkoClient` and/or `JinkoOrgClient`, and optionally the exceptions from `jinko`. The SDK has no `jinko.model` or `jinko.models` module. Get every other object from the client, then read its signature and docstring when needed with `help()`:

```python
model = client.get_model("cm-...")
help(client.get_model)
help(type(model))  # every method of the returned object
help(model.simple_solve)
```

Import a class from `jinko.domain` only to name it in a type annotation, for example `from jinko.domain import Model`. Avoid searching the installed package source for signatures.

## Choosing a client

Both clients accept a project key and an organization key, so choose by task. Use `JinkoClient()` for work in the project that `JINKO_PROJECT_ID` names. Use `JinkoOrgClient` when `JINKO_PROJECT_ID` is unset or the task spans several projects. `JinkoOrgClient` reads `JINKO_API_KEY` and `JINKO_BASE_URL` only:

```python
from jinko import JinkoOrgClient

org = JinkoOrgClient()
for project in org.list_projects():
    print(project.id, project.name)

client = org.project(project.id)  # a JinkoClient for that project
```

Use `org.auth_check()` to read the key's declared scope without a project ID.
`list_projects()` can include projects outside that scope. In a multi-project
workflow, call `client.auth_check()` on each project client and catch
`AuthenticationError` to skip an out-of-scope project. Then request a project
resource to verify actual access. Authentication responses without key metadata
receive a credential check only.

## Troubleshooting

Run the check again and act on its deterministic diagnostic. Do not replace it with ad hoc checks or ask the user to share secrets.
