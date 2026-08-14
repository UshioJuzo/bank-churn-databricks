-- =============================================================================
-- WHAT THIS FILE DOES
--   Creates the modelled layer: the typed customer table with its constraints,
--   the scoring-run provenance table, the prediction history that reverse ETL
--   writes into, and the view the application reads.
--
-- WHERE IT RUNS
--   The Lakebase SQL editor (Postgres 17).
--
-- WHEN
--   Phase 2 of 2. AFTER customers_raw is loaded and after the eight data
--   checks (V1 to V8) in notebook 01 have passed.
--
-- STATUS
--   Executed. The CHECK bounds below were adjusted to the ranges actually
--   observed in V4, so they are facts now, not expectations.
-- =============================================================================
--
-- Why the order matters: the constraints here encode what V1 to V8 found. If
-- this file ran first, a bound guessed wrong would reject real rows and the
-- finding would be lost instead of documented.

-- -----------------------------------------------------------------------------
-- customers - typed, keyed and constrained
--
-- surname is deliberately not carried over from the landing table. The privacy
-- constraint is imposed by the schema, not by the discipline of whoever writes
-- the query. A column that does not exist cannot be leaked by accident.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_churn.customers (
    customer_id       BIGINT        PRIMARY KEY,
    geography_id      SMALLINT      NOT NULL REFERENCES bank_churn.geographies,
    gender            TEXT          NOT NULL CHECK (gender IN ('Male','Female')),
    age               SMALLINT      NOT NULL CHECK (age BETWEEN 18 AND 120),
    tenure            SMALLINT      NOT NULL CHECK (tenure BETWEEN 0 AND 10),
    credit_score      SMALLINT      NOT NULL CHECK (credit_score BETWEEN 300 AND 900),
    balance           NUMERIC(14,2) NOT NULL CHECK (balance >= 0),
    estimated_salary  NUMERIC(14,2) NOT NULL CHECK (estimated_salary >= 0),
    num_of_products   SMALLINT      NOT NULL CHECK (num_of_products BETWEEN 1 AND 4),
    has_cr_card       BOOLEAN       NOT NULL,
    is_active_member  BOOLEAN       NOT NULL,
    exited            BOOLEAN       NOT NULL,
    _loaded_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);

COMMENT ON TABLE bank_churn.customers IS
    'Operational customer record. surname excluded on purpose: privacy enforced by the schema.';

CREATE INDEX IF NOT EXISTS idx_customers_geography ON bank_churn.customers (geography_id);
CREATE INDEX IF NOT EXISTS idx_customers_exited    ON bank_churn.customers (exited);

-- -----------------------------------------------------------------------------
-- model_runs - provenance, not analytics
--
-- It stores no evaluation metric, and that is deliberate: those live in
-- gold.model_metrics on the Delta side, where their audience is. What stays
-- here is what answers an operational question from the CRM: "why did this
-- customer's risk level change between September and November?"
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_churn.model_runs (
    model_run_id        BIGSERIAL    PRIMARY KEY,
    model_name          TEXT         NOT NULL,
    model_version       TEXT         NOT NULL,
    decision_threshold  NUMERIC(5,4) NOT NULL CHECK (decision_threshold BETWEEN 0 AND 1),
    trained_at          TIMESTAMPTZ  NOT NULL,
    notes               TEXT,
    UNIQUE (model_name, model_version)
);

COMMENT ON TABLE bank_churn.model_runs IS
    'Provenance of each scoring run. Evaluation metrics excluded on purpose.';

-- -----------------------------------------------------------------------------
-- customer_predictions - reverse ETL target, consumed by the retention team
--
-- The primary key is composite because the history is append-only: one row per
-- customer per run. That way what was predicted at a given moment can be
-- reconstructed, instead of overwriting the past.
--
-- The risk_level cuts are decided in notebook 05 by the method fixed in
-- advance: operating capacity leads, and the expected-cost threshold is the
-- cross-check.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_churn.customer_predictions (
    customer_id        BIGINT       NOT NULL REFERENCES bank_churn.customers,
    model_run_id       BIGINT       NOT NULL REFERENCES bank_churn.model_runs,
    churn_probability  NUMERIC(6,5) NOT NULL CHECK (churn_probability BETWEEN 0 AND 1),
    predicted_class    BOOLEAN      NOT NULL,
    risk_level         TEXT         NOT NULL CHECK (risk_level IN ('low','medium','high')),
    scored_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (customer_id, model_run_id)
);

COMMENT ON TABLE bank_churn.customer_predictions IS
    'Reverse ETL target. Append-only: one row per customer per scoring run.';

CREATE INDEX IF NOT EXISTS idx_pred_risk ON bank_churn.customer_predictions (risk_level);
CREATE INDEX IF NOT EXISTS idx_pred_prob ON bank_churn.customer_predictions (churn_probability DESC);

-- -----------------------------------------------------------------------------
-- Latest score per customer. This is what the application reads.
--
-- DISTINCT ON is Postgres-specific and does here what a window function would
-- need three more lines to express: keep the first row of each customer_id
-- group, given the ordering below.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW bank_churn.v_latest_predictions AS
SELECT DISTINCT ON (customer_id)
       customer_id,
       model_run_id,
       churn_probability,
       predicted_class,
       risk_level,
       scored_at
FROM   bank_churn.customer_predictions
ORDER  BY customer_id, scored_at DESC;

-- -----------------------------------------------------------------------------
-- Verification
-- -----------------------------------------------------------------------------
SELECT table_name, table_type
FROM   information_schema.tables
WHERE  table_schema = 'bank_churn'
ORDER  BY table_type, table_name;
