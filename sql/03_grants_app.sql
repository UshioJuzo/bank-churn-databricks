-- =============================================================================
-- WHAT THIS FILE DOES
--   Grants a Databricks App's service principal the minimum it needs to read
--   the gold schema and load the registered model.
--
-- WHERE IT RUNS
--   The DATABRICKS SQL editor (Unity Catalog), NOT the Lakebase one.
--
-- STATUS
--   DOCUMENTARY. Kept as a record of how the original deployment worked.
--
--   In this version the public application does not query the warehouse: it
--   reads a parquet snapshot exported by notebook 06, so it needs no
--   credentials and no permissions at all. These grants are therefore not
--   required for anything here to run.
--
--   They are kept because the reasoning is the interesting part, and because
--   the error described below cost real time to diagnose.
-- =============================================================================
--
-- A Databricks App runs as its own service principal and does NOT inherit the
-- permissions of whoever created it. Without these grants the app deploys
-- cleanly and then fails on its first query, with a permissions error.

-- The app's service principal. The identifier is copied from
-- Apps > <app> > Settings, where it appears as the client id.
--   <service-principal-id>

GRANT USE CATALOG ON CATALOG bank_churn_eng
    TO `<service-principal-id>`;

GRANT USE SCHEMA ON SCHEMA bank_churn_eng.gold
    TO `<service-principal-id>`;

-- Granting SELECT on the whole schema also covers future tables, so adding a
-- table to gold tomorrow does not mean coming back here.
GRANT SELECT ON SCHEMA bank_churn_eng.gold
    TO `<service-principal-id>`;

-- -----------------------------------------------------------------------------
-- The registered model
-- -----------------------------------------------------------------------------
-- MLflow experiments have their own access control lists, separate from the
-- catalog's. An app loading a model by runs:/<run_id> gets "Run not found",
-- a message that misleads: what it actually means is "you have no permission
-- on the experiment".
--
-- Some systems hide the existence of a resource from anyone who cannot see it,
-- so a not-found error can be a permissions error wearing a disguise.
--
-- The correct fix was not to grant access to the experiment, but to register
-- the model in Unity Catalog, which puts it under the same permission system
-- as the tables.

-- Syntax note: in this version of Unity Catalog registered models are treated
-- as functions, so it is ON FUNCTION, not ON MODEL.
GRANT EXECUTE ON FUNCTION bank_churn_eng.gold.churn_model
    TO `<service-principal-id>`;

-- -----------------------------------------------------------------------------
-- What is deliberately NOT granted
-- -----------------------------------------------------------------------------
-- No access to bronze or silver. The application has no business with raw or
-- intermediate data. Least privilege: if it is ever compromised, the blast
-- radius is a table of predictions that was already in the CRM.

-- -----------------------------------------------------------------------------
-- Verification
-- -----------------------------------------------------------------------------
SHOW GRANTS `<service-principal-id>` ON SCHEMA bank_churn_eng.gold;

-- Expect USE SCHEMA and SELECT. Nothing on bronze, nothing on silver.
