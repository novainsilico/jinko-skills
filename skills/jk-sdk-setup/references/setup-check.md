# Setup Check Reference

Use this reference when explaining what `scripts/check_jinko_connection.py` verifies.

## What The Check Proves

- The active Python environment can import `jinko`.
- `.env` loading works when `python-dotenv` is installed.
- `JINKO_API_KEY` and `JINKO_PROJECT_ID` are present before the SDK client is constructed.
- `JinkoClient()` can read credentials from the environment.
- `client.auth_check()` can authenticate on the selected project.

## What To Use Next For Exploration

After the setup check succeeds, switch to `client.search(...)` for read-only project exploration.

- Use `search()` when the user wants to browse project items, search by text, or get oriented before choosing a workflow-specific skill.
- A good default is `client.search(limit=20, table_columns="compact")`.

## Expected Outcomes

- Success: `jinkō connection OK`.
- Missing config: set `JINKO_API_KEY` and `JINKO_PROJECT_ID`, using `assets/.env.example` as a template.
- Missing API key: create one using `https://doc.jinko.ai/docs/api/`.
- Authentication refused: rotate or re-copy the API key.
- Authorization refused: verify that the key has access to the configured project.
