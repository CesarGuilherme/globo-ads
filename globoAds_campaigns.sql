-- ============================================================================
-- GLOBO ADS — Digital items + demographic → airbyte_secom  (deployment DDL)
-- ============================================================================
-- Source: POST /api/v1/digital/items + POST /api/v1/digital/demographic (Globo Ads
-- "Resultados" API), SECOM account. Loader: globo-ads/extract.py (run from n8n:
-- Schedule -> Execute Command). Three tables: globoAds_campaigns (items),
-- globoAds_demographic (age/gender/region), globoAds_runs (shared audit ledger).
--
-- Date-partition replace model: /digital/items has NO row-level key (rows can match on
-- every visible field yet differ only in a hidden impression segment, ~2% are
-- byte-identical), so we can't upsert per row. But `date` is a clean partition: each
-- load does DELETE WHERE date BETWEEN start AND end, then INSERT, in one transaction.
-- This prevents cross-run duplication (retries, overlapping windows, Globo restatements
-- all replace a day instead of stacking it). The table is queried directly — every date
-- present once; run_id/extracted_at are provenance and globoAds_runs is the audit ledger.
-- A no-arg extract.py run gap-fills MAX(date)+1 .. yesterday (America/Sao_Paulo).
-- (Deliberate divergence from the house "INSERT ... ON DUPLICATE KEY UPDATE" rule — there
-- is no natural row key.) Field names preserved from the API (incl. the codCampaing typo).
-- Money is DECIMAL(14,2); seconds is a VARCHAR ("Outros"); video_vtr is a count, not a rate.
-- ============================================================================

CREATE TABLE IF NOT EXISTS airbyte_secom.globoAds_campaigns (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id       BIGINT   NOT NULL,
    extracted_at DATETIME NOT NULL,

    -- Dimensions
    `date`                 DATE,
    codLineItem            BIGINT,
    lineItem               VARCHAR(500),
    creative               VARCHAR(500),
    project                VARCHAR(255),
    codCampaing            VARCHAR(50),
    campaign               VARCHAR(500),
    codClient              BIGINT,
    nameClient             VARCHAR(255),
    codAgency              BIGINT,
    nameAgency             VARCHAR(255),
    product                VARCHAR(100),
    `format`               VARCHAR(100),
    campaignType           VARCHAR(50),
    platform               VARCHAR(255),
    seconds                VARCHAR(50),
    device                 VARCHAR(50),
    midia                  VARCHAR(100),

    -- Metrics
    clicks                            BIGINT,
    impression_impressionsContracted  BIGINT,
    impression_impressionsDelivered   BIGINT,
    video_viewAll                     BIGINT,
    video_viewTwentyFive              BIGINT,
    video_viewFifty                   BIGINT,
    video_viewSeventyFive             BIGINT,
    video_vtr                         BIGINT,
    investment_lineItem               DECIMAL(14,2),
    investment_campaign               DECIMAL(14,2),

    INDEX idx_run (run_id),
    INDEX idx_date (`date`),
    INDEX idx_campaign (codCampaing)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Run ledger (refresh_log style) — one row per extraction run.
CREATE TABLE IF NOT EXISTS airbyte_secom.globoAds_runs (
    run_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    start_date     DATE,
    end_date       DATE,
    started_at     DATETIME NOT NULL,
    finished_at    DATETIME NULL,
    total_elements INT NULL,
    received       INT NULL,
    status         ENUM('RUNNING','SUCCESS','ERROR') NOT NULL DEFAULT 'RUNNING',
    error_message  TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================================
-- Demographic breakdown (age/gender/region) — airbyte_secom.globoAds_demographic
-- ============================================================================
-- Source: POST /api/v1/digital/demographic, one call per campaign (batching multiple
-- campaign names per call 504s the gateway). Only `ages`/`genders`/`region` are
-- extracted (out of scope: interests/purchaseIntention/territory/consumptionPotential).
-- All three arrays share an identical row shape and are unioned into one table,
-- discriminated by `profileDomain` ("Faixa Etaria" | "Genero" | "Regiao" — verbatim
-- from the API). `ctr`/`impressions`/`clicks` here are PERCENTAGES (0-100), not raw
-- counts — do not confuse with globoAds_campaigns' raw-count `clicks`/`impression_*`.
--
-- Availability is gated by two server-side factors (verified live 2026-06-30, not
-- documented by the apiDoc): campaignType='DAI-A' never has demographic data, regardless
-- of recency or volume; everything else has a rolling recency window of ~190-220 days
-- before "today" (the exact boundary is fuzzy — see DEMOGRAPHIC_LOOKBACK_DAYS in
-- extract.py). Impression volume does NOT gate availability once in-window.
--
-- Load model: campaign-partition replace (not date-partitioned — this is a per-campaign
-- snapshot, re-fetched fresh each run for every currently in-window, non-DAI-A campaign).
-- Each run does DELETE WHERE codCampaign IN (<campaigns successfully queried this run>)
-- then INSERT, sharing globoAds_runs.run_id with the items load for the same execution.
-- A campaign whose API call fails this run keeps its prior snapshot untouched (retried
-- next run); a campaign that ages out of the lookback window is simply never revisited
-- again (its last-known snapshot is frozen, not deleted).
--
-- NOTE the column is `codCampaign` (correctly spelled) here, vs. globoAds_campaigns'
-- `codCampaing` (typo, kept verbatim from /digital/items) — do not conflate when joining.
-- ============================================================================

CREATE TABLE IF NOT EXISTS airbyte_secom.globoAds_demographic (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id       BIGINT   NOT NULL,
    extracted_at DATETIME NOT NULL,

    -- Parent campaign context (repeated per row; one /digital/demographic call per campaign)
    startDate    DATE,
    endDate      DATE,
    project      VARCHAR(255),
    codCampaign  VARCHAR(50),
    campaign     VARCHAR(500),
    codClient    BIGINT,
    nameClient   VARCHAR(255),
    codAgency    BIGINT,
    nameAgency   VARCHAR(255),

    -- Profile breakdown row (one per ages[]/genders[]/region[] element)
    profileDomain VARCHAR(50),
    codOrder      VARCHAR(50),
    label         VARCHAR(255),
    ctr           DECIMAL(10,4),
    impressions   DECIMAL(10,4),
    clicks        DECIMAL(10,4),

    INDEX idx_run (run_id),
    INDEX idx_campaign (codCampaign),
    INDEX idx_domain (profileDomain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Current snapshot (latest successful run):
--   SELECT c.* FROM airbyte_secom.globoAds_campaigns c
--   WHERE c.run_id = (SELECT MAX(run_id) FROM airbyte_secom.globoAds_runs WHERE status='SUCCESS');
--
-- Latest demographic snapshot for a campaign:
--   SELECT profileDomain, label, ctr, impressions, clicks
--   FROM airbyte_secom.globoAds_demographic WHERE codCampaign = '88398';
