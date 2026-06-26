-- ============================================================================
-- GLOBO ADS — Digital items → airbyte_secom  (deployment DDL)
-- ============================================================================
-- Source: POST /api/v1/digital/items (Globo Ads "Resultados" API), SECOM account.
-- Loader: globo-ads/extract.py (run from n8n: Schedule -> Execute Command).
--
-- Append-only model: /digital/items has NO unique dimensional grain (rows can match
-- on every visible field yet differ only in a hidden impression segment, ~2% are
-- byte-identical), so we do NOT upsert. Each run appends a verbatim snapshot tagged
-- with run_id + extracted_at; downstream reads MAX(run_id). This is a deliberate
-- divergence from the house "INSERT ... ON DUPLICATE KEY UPDATE" rule — there is no
-- natural key to dedupe on. Field names preserved from the API (incl. the codCampaing
-- typo). Money is DECIMAL(14,2); seconds is a VARCHAR ("Outros"); video_vtr is a
-- small-integer count, not a rate.
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
