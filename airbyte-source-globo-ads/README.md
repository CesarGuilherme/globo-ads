# source-globo-ads

Conector Airbyte (Python CDK) para a API Globo Ads Resultados. Substitui a
extração que roda hoje no n8n via `extract.py`.

## Streams

| Stream | Endpoint | Modo | Janela |
|---|---|---|---|
| `digital_items` | `POST /digital/items` | incremental + append | 31 dias |
| `digital_demographic` | `POST /digital/demographic` | full_refresh + append | 1 POST por campanha |

`/digital/items` **não tem PK**. O destino deve ser `append`; o silver fica com o
último `_airbyte_extracted_at` por `date`. Não usar `append_dedup`.

Auth: token de plataforma no header `Authorization` **sem** `Bearer`.

`end_date` é sempre ontem `America/Sao_Paulo`. Resume no cursor, sem `+1`.
Lookback default 7 dias.

## Rodando local

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -e . && pip install pytest requests-mock pytest-mock

python main.py spec
python main.py check    --config secrets/config.json
python main.py discover --config secrets/config.json
python main.py read     --config secrets/config.json --catalog integration_tests/configured_catalog.json
python -m pytest unit_tests/ -q
```

`secrets/config.json` nunca é versionado. Campos: `api_token`, `cod_client`, e
opcionalmente `start_date`, `end_date`, `lookback_window_days`, `window_in_days`,
`page_size`, `demographic_lookback_days`.

## Build e publicação

```bash
docker build --platform linux/amd64 -t digitalbsb/source-globo-ads:0.1.0 .
docker run --rm digitalbsb/source-globo-ads:0.1.0 spec
docker push digitalbsb/source-globo-ads:0.1.0
```

Import no Airbyte self-hosted: **Settings → Sources → New connector → Add a new Docker
connector**, repositório `digitalbsb/source-globo-ads`, tag `0.1.0`. Prefix da
connection: `globoads_air`.
