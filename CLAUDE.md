# CLAUDE.md

Python 3.10+ client and **Airbyte source** for the Globo Ads Resultados API.

## Extraction (current)

Daily extraction is an Airbyte custom source, not the n8n `extract.py` job.

- Connector: `airbyte-source-globo-ads/` (CDK 7, Python 3.11)
- Image: `digitalbsb/source-globo-ads:0.1.0`
- Streams: `digital_items` (incremental append, no PK), `digital_demographic` (full refresh)
- Destination tables (connection prefix `globoads_air`):
  `globoads_air_digital_items`, `globoads_air_digital_demographic`
- Auth: platform token in a **bare** `Authorization` header (no Bearer)
- Base: `https://api-ads-resultados.mybackstage.globo.com/api/v1/`
- `end_date` = yesterday `America/Sao_Paulo`; resume at cursor, no `+1`; lookback 7 days
- `/digital/items` has **no unique grain** — do not append_dedup. Silver keeps latest
  `_airbyte_extracted_at` per `date`. See Brain `digital_data_model_quirks`.

`extract.py` remains as a manual probe/backfill tool. Do not schedule it.

## Local connector

```bash
cd airbyte-source-globo-ads
/opt/homebrew/bin/python3.11 -m venv .venv && source .venv/bin/activate
pip install -e . && pip install pytest requests-mock pytest-mock
python main.py spec|check|discover --config secrets/config.json
python -m pytest unit_tests/ -q
```

## Secrets

`.env` at repo root (`api_token`, `cod_client`, `MYSQL_*`). Never commit `.env` or
`airbyte-source-globo-ads/secrets/config.json`. Preserve API field names as-is
(including the `codCampaing` typo).
