-- =============================================================================
-- WHAT THIS FILE DOES
--   Creates the landing layer in Lakebase: the schema, the raw table that
--   receives churn.csv unchanged, and the country lookup table.
--
-- WHERE IT RUNS
--   The Lakebase SQL editor (Postgres 17), NOT the Databricks SQL editor.
--   Two different engines.
--
-- WHEN
--   Phase 1 of 2. Before loading any data. Notebook 01 depends on it.
--
-- STATUS
--   Executed. This is the schema the sandbox branch currently runs on.
-- =============================================================================
--
-- There is deliberately not a single constraint in this file. If the source
-- file carries bad values they have to land and stay auditable, not be
-- rejected in silence. The quality rules live in phase 2 (02_modeled.sql),
-- where a violation becomes a documented finding instead of a lost record.

CREATE SCHEMA IF NOT EXISTS bank_churn;

-- -----------------------------------------------------------------------------
-- customers_raw - a faithful copy of churn.csv
--
-- Column names are normalised to snake_case because Postgres lower-cases any
-- identifier that is not quoted: keeping "CustomerId" would mean quoting it in
-- every single query.
--
-- Values are never altered. This table is a literal copy of the source so that
-- later we can prove what came from the file and what we added ourselves.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_churn.customers_raw (
    row_number        INTEGER,
    customer_id       BIGINT,
    surname           TEXT,
    credit_score      INTEGER,
    geography         TEXT,
    gender            TEXT,
    age               INTEGER,
    tenure            INTEGER,
    balance           NUMERIC(14,2),
    num_of_products   INTEGER,
    has_cr_card       SMALLINT,
    is_active_member  SMALLINT,
    estimated_salary  NUMERIC(14,2),
    exited            SMALLINT,

    -- Provenance metadata. This is what lets us answer where each row came
    -- from, when it arrived and from which file.
    _ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    _source_file      TEXT        NOT NULL,
    _source_url       TEXT
);

COMMENT ON TABLE bank_churn.customers_raw IS
    'Landing table. Immutable copy of the source file. No constraints, on purpose.';

-- -----------------------------------------------------------------------------
-- geographies - lookup table
--
-- The only honest normalisation this dataset allows: three fixed countries.
-- It exists so an ISO code, a currency or a region can be added tomorrow
-- without touching the customer table.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_churn.geographies (
    geography_id  SMALLINT PRIMARY KEY,
    country_name  TEXT    NOT NULL UNIQUE,
    iso_code      CHAR(2) NOT NULL UNIQUE
);

INSERT INTO bank_churn.geographies (geography_id, country_name, iso_code) VALUES
    (1, 'France',  'FR'),
    (2, 'Spain',   'ES'),
    (3, 'Germany', 'DE')
ON CONFLICT (geography_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Verification
-- -----------------------------------------------------------------------------
SELECT table_name
FROM   information_schema.tables
WHERE  table_schema = 'bank_churn'
ORDER  BY table_name;

SELECT * FROM bank_churn.geographies;
