-- ============================================================================
-- GLOBO ADS — Digital items → airbyte_secom  (deployment DDL)
-- ============================================================================
-- Source: POST /api/v1/digital/items (Globo Ads "Resultados" API), SECOM account.
-- Loader: globo-ads/extract.py (run from n8n: Schedule -> Execute Command).
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

-- Current snapshot (latest successful run):
--   SELECT c.* FROM airbyte_secom.globoAds_campaigns c
--   WHERE c.run_id = (SELECT MAX(run_id) FROM airbyte_secom.globoAds_runs WHERE status='SUCCESS');
