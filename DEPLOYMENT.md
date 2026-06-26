# Deployment — Globo Ads Extraction

Daily extraction of `/digital/items` into the shared MySQL warehouse `airbyte_secom`, run by n8n.

## Host
- Server: `cesar@172.25.12.207` (n8n runs in Docker; container name **`n8n-app`**, image `server-n8n`).
- Code lives on the host at **`~/server/globo-ads-extraction/`**, bind-mounted into the container at
  **`/home/node/server/globo-ads-extraction/`**.
- Container already provides: system **python3.12** with `requests` / `pymysql` / `python-dotenv`,
  `tzdata` (zoneinfo `America/Sao_Paulo`), `TZ=America/Sao_Paulo`, `N8N_EXECUTE_COMMAND_ENABLED=true`.
  No virtualenv needed.

## Files deployed
`client.py`, `extract.py`, `requirements.txt`, plus `.env` (chmod **600**, not in git) holding
`api_token`, `cod_client`, `MYSQL_*`, and `N8N_API_*`. (`probe.py` / `phase0.py` / `check_token.py`
are copied too as one-off ops tools but are not part of the scheduled run.)

## n8n workflow
- Name **"Globo Ads Extraction"**, id **`0Tfw75IRQ60NtGf0`**, **active**.
- Schedule Trigger → Execute Command `python3 /home/node/server/globo-ads-extraction/extract.py`
  (`retryOnFail: true`, 5s backoff).
- Schedule: daily **01:00 America/Sao_Paulo** (`triggerAtHour:1`) — staggered after the 00:00
  Amazon DSP / Metrike extractors, before the 07:30 Creative Classification job.
- Error workflow: `ydYmN_AWi27C953XOLCqR` (shared "Amazon Ads Error" alert, same as siblings).

## Behavior
No-arg run gap-fills `MAX(date)+1 .. yesterday(SP)`; idempotent per date (DELETE range + INSERT),
so retries / overlaps / Globo restatements never duplicate a day. Each run logged in
`globoAds_runs` (status `RUNNING`→`SUCCESS`/`ERROR`).

## Common ops (from the host)
```bash
# manual run (gap-fill; no-op if already current)
docker exec n8n-app sh -lc 'cd /home/node/server/globo-ads-extraction && python3 extract.py'
# backfill / re-pull an explicit range (idempotent)
docker exec n8n-app sh -lc 'cd /home/node/server/globo-ads-extraction && python3 extract.py 2024-01-01 2024-12-31'
# redeploy code after changes (from the repo)
sshpass -p <pw> scp client.py extract.py requirements.txt cesar@172.25.12.207:~/server/globo-ads-extraction/
```

## n8n management
Public REST API on the host: `http://localhost:5678/api/v1`, header `X-N8N-API-KEY` (key in `.env`
as `N8N_API_KEY`; also exposed via ngrok at `N8N_API_URL`). Note: `n8n execute` CLI does **not** work
inside the running container (task-broker port 5679 conflict); trigger from the UI or let the
schedule fire. The MySQL deployment DDL is `globoAds_campaigns.sql`.
```
