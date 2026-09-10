# Deployment — Globo Ads Airbyte source

Replaces the n8n Execute Command job (`extract.py` on `172.25.12.207`).

## Image

```bash
cd airbyte-source-globo-ads
docker build --platform linux/amd64 -t digitalbsb/source-globo-ads:0.1.1 .
docker push digitalbsb/source-globo-ads:0.1.1
```

Hub repo: **`digitalbsb/source-globo-ads`** (public). Docker Desktop is logged in as `digitalbsb`.

## Airbyte (OKE)

Access: SSH `secom_admin@163.176.227.241`, then `kubectl` in namespace `airbyte-prod`.
Mac `~/.kube/config` is empty — do not treat that as an outage.

1. Settings → Sources → Add a new Docker connector
   - Repository: `digitalbsb/source-globo-ads`
   - Tag: `0.1.1`
2. Create source with `api_token` + `cod_client` (258469). Optional: `start_date=2023-01-01`.
3. Connection to MySQL `airbyte_secom`, prefix **`globoads_air`**, streams:
   - `digital_items` — incremental / append (not append_dedup)
   - `digital_demographic` — full refresh / append
4. Schedule ~01:00 America/Sao_Paulo.
5. First sync is a historical load from 2023-01-01.

## Silver

After the first sync lands rows, apply `oracle/mysql/globoads_airbyte_retarget.sql`
and point `pipeline_health_check.sql` at `globoads_air_digital_items` /
`MAX(_airbyte_extracted_at)`. Then:

```sql
CALL airbyte_secom.sp_migrate_globoads_campaigns(NULL, NULL);
```

Compare `SUM(impressions)` / `SUM(spend)` against `globoAds_campaigns` on the overlap
through 2026-09-04. Do not change `silver_globoads_campaigns` or gold shapes.

## n8n (legacy)

Workflow **"Globo Ads Extraction"** id `0Tfw75IRQ60NtGf0` — deactivate after the
Airbyte connection is green. Keep the workflow; do not delete until numbers are
signed off. `extract.py` on the n8n host can stay as a manual tool.
