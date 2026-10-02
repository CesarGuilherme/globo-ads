# globo-ads

Extração da API **Globo Ads Resultados** (`/digital/*`) da conta SECOM para o
warehouse MySQL `airbyte_secom`.

A extração diária roda como **source customizado do Airbyte**
([`airbyte-source-globo-ads/`](airbyte-source-globo-ads/README.md)). Os scripts na raiz
são ferramentas manuais de sondagem e backfill.

## Estrutura

| Caminho | O que é |
|---|---|
| `airbyte-source-globo-ads/` | Conector Airbyte (CDK 7, Python 3.11), imagem `digitalbsb/source-globo-ads` |
| `DEPLOYMENT.md` | Build da imagem, setup no Airbyte, silver e desligamento do n8n |
| `client.py` | Cliente compartilhado: base URL, token do `.env`, `post()` e `paginate()` |
| `check_token.py` | Valida o token de plataforma do `.env` |
| `probe.py` | Descobre quais grupos de plataforma têm dados para a conta |
| `phase0.py` | Checagens de grão e paginação de `/digital/items` |
| `extract.py` | Extrator legado (n8n) → MySQL. Uso manual; não agendar |
| `globoAds_campaigns.sql` | DDL das tabelas legadas (`globoAds_*`) |
| `delete_run_1.sql` | Limpeza pontual de uma execução de teste |
| `Gads Results API Documentation pt-BR.html` | Documentação oficial da API |

## API

- Base: `https://api-ads-resultados.mybackstage.globo.com/api/v1/`
- Auth: token de plataforma no header `Authorization`, **sem** `Bearer`
- Streams do conector: `digital_items` (incremental/append) e `digital_demographic`
  (full refresh); prefixo no destino `globoads_air`
- `/digital/items` **não tem grão único**: nunca usar `append_dedup`. O silver fica com
  o último `_airbyte_extracted_at` por `date`
- Os nomes de campo da API são preservados como vêm (inclusive o typo `codCampaing`)

## Uso local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 check_token.py           # valida o token
python3 probe.py                 # sonda as plataformas
python3 extract.py 2026-09-01 2026-09-07   # backfill manual de um intervalo
```

O conector tem instruções próprias em
[`airbyte-source-globo-ads/README.md`](airbyte-source-globo-ads/README.md).

## Configuração

`.env` na raiz (nunca versionado): `api_token`, `cod_client`, `MYSQL_*`.
O conector lê `airbyte-source-globo-ads/secrets/config.json` (também fora do git; veja
`config.json.template`).
