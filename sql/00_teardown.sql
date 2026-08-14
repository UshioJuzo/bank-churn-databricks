-- =============================================================================
-- WHAT THIS FILE DOES
--   Wipes the bank_churn schema so the pipeline can be rebuilt from zero.
--   Also documents the partial resets, which are what you actually use most
--   of the time.
--
-- WHERE IT RUNS
--   The Lakebase SQL editor (Postgres 17).
--
-- WHEN
--   Only when you want to start over. It is numbered 00 because it is the
--   point zero of a rebuild, not because it runs first in the normal flow.
--
-- STATUS
--   Executed once, to rebuild the sandbox branch from scratch. It works.
--
-- DESTRUCTIVE. Rebuilding afterwards takes about two minutes:
--   00_teardown.sql -> 01_landing.sql -> notebook 01 -> 02_modeled.sql
-- =============================================================================
--
-- Safer alternative to deleting anything: create a Lakebase branch, break
-- things there, and drop the branch afterwards. Production is never touched.
--
--   databricks postgres create-branch projects/bank-churn-prediction sandbox \
--     --json '{"spec": {"source_branch": "projects/bank-churn-prediction/branches/production", "ttl": "86400s"}}'

-- Look before you delete: exactly how much is about to be lost
SELECT 'customers_raw'         AS table_name, COUNT(*) AS rows FROM bank_churn.customers_raw
UNION ALL
SELECT 'customers',                 COUNT(*) FROM bank_churn.customers
UNION ALL
SELECT 'customer_predictions',      COUNT(*) FROM bank_churn.customer_predictions
UNION ALL
SELECT 'model_runs',                COUNT(*) FROM bank_churn.model_runs;

-- -----------------------------------------------------------------------------
-- Uncomment to run. CASCADE resolves the foreign key order on its own, so the
-- tables do not have to be dropped one by one.
--
-- It is commented deliberately: a full wipe should not be one click away.
-- -----------------------------------------------------------------------------
-- DROP SCHEMA IF EXISTS bank_churn CASCADE;

-- -----------------------------------------------------------------------------
-- Partial resets. These are almost always enough, and far less destructive
-- -----------------------------------------------------------------------------

-- Reload only the source data (keeps the schema and the modelled tables):
--   TRUNCATE TABLE bank_churn.customers_raw;

-- Drop predictions and scoring runs, keeping the customers:
--   TRUNCATE TABLE bank_churn.customer_predictions;
--   TRUNCATE TABLE bank_churn.model_runs RESTART IDENTITY CASCADE;

-- Rebuild the operational record from the landing table:
--   TRUNCATE TABLE bank_churn.customers CASCADE;
--   -- then re-run the load cell in notebook 01

-- =============================================================================
-- The Delta side. This runs in a notebook, not here:
--
--   spark.sql("DROP SCHEMA IF EXISTS bank_churn_eng.bronze CASCADE")
--   spark.sql("DROP SCHEMA IF EXISTS bank_churn_eng.silver CASCADE")
--   spark.sql("DROP SCHEMA IF EXISTS bank_churn_eng.gold   CASCADE")
--
-- Or the whole analytical catalog in one line:
--   spark.sql("DROP CATALOG IF EXISTS bank_churn_eng CASCADE")
--
-- Careful: Delta keeps history. A managed table that is dropped is gone, but
-- one that was merely overwritten can be recovered by time travel:
--   SELECT * FROM bank_churn_eng.bronze.customers_raw VERSION AS OF 3
-- =============================================================================
