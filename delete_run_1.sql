-- Delete the stale test run (run_id = 1: range 2024-05-01..2025-07-31) from the
-- shared airbyte_secom warehouse. Scoped DELETE — does NOT touch other runs.
-- Current snapshot (run_id = 2, 2023-01-01..2026-06-25) is unaffected.

USE airbyte_secom;

START TRANSACTION;

-- 1. data rows for run 1
DELETE FROM globoAds_campaigns WHERE run_id = 1;

-- 2. the ledger entry for run 1
DELETE FROM globoAds_runs WHERE run_id = 1;

COMMIT;

-- Verify afterwards:
--   SELECT run_id, start_date, end_date, received, status FROM globoAds_runs;
--   SELECT COUNT(*) FROM globoAds_campaigns;          -- expect 95271
--   SELECT COUNT(*) FROM globoAds_campaigns WHERE run_id = 1;  -- expect 0
