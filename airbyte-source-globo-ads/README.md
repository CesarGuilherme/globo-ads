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
docker build --platform linux/amd64 -t digitalbsb/source-globo-ads:0.1.1 .
docker run --rm digitalbsb/source-globo-ads:0.1.1 spec
docker push digitalbsb/source-globo-ads:0.1.1
```

A imagem precisa ser `linux/amd64` (os nós do Airbyte são x86) e o repositório no
Docker Hub é público, então o Airbyte puxa sem `imagePullSecret`.

## Instalar no Airbyte (custom source)

Funciona no Airbyte self-hosted (OSS / abctl / Helm). O Airbyte Cloud não aceita
imagens Docker customizadas.

1. **Registrar o conector**: *Settings → Sources → **+ New connector** → **Add a new
   Docker connector***.
   - Connector display name: `Globo Ads`
   - Docker repository name: `digitalbsb/source-globo-ads`
   - Docker image tag: `0.1.1`
   - Connector documentation URL: opcional

   O Airbyte puxa a imagem e roda `spec`. Se falhar, confira o nome e a tag e se a
   imagem foi publicada como `linux/amd64`.
2. **Criar o source**: *Sources → **+ New source***, busque **Globo Ads** e preencha
   - `API Token`: o token de plataforma (sem `Bearer`)
   - `Client Code`: o `codClient` da conta
   - opcional: `Start Date` (ex.: `2023-01-01` para a carga histórica) e os demais
     campos de janela/paginação

   *Set up source* roda `check`, que precisa passar.
3. **Criar a connection** com o destino MySQL:
   - Destination namespace/prefix: `globoads_air`
   - `digital_items`: **Incremental | Append** (não usar *Append + Deduped*; o
     endpoint não tem PK)
   - `digital_demographic`: **Full refresh | Append**
   - Schedule: diário, ~01:00 America/Sao_Paulo
4. Rode *Sync now* uma vez e confira as linhas em `globoads_air_digital_items`.

### Atualizar a versão

Publique a nova tag (`docker build … && docker push`) e troque a tag em
*Settings → Sources → Globo Ads → Change version*. Mudança de schema pede
*Refresh source schema* na connection.

Detalhes do ambiente da SECOM (acesso ao cluster, silver, desligamento do n8n) ficam
em [`../DEPLOYMENT.md`](../DEPLOYMENT.md).
