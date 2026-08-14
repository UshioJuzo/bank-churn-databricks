"""
Shared bootstrap for every notebook in this project.

The notebooks run from a local machine and push the computation to Databricks
through Databricks Connect. Nothing here is specific to a notebook: it is the
connection, the resource names, and the two helpers that talk to Lakebase.

Usage, first cell of every notebook:

    import sys; sys.path.append("../src")
    from config import bootstrap

    ctx = bootstrap()
    spark, w = ctx.spark, ctx.w

Credentials never appear in this file. They are read from a local `.env` that
is excluded from version control -- see `.env.example` for the shape of it.
"""

from __future__ import annotations

import os
import ssl
import datetime as dt
from dataclasses import dataclass, field

# ---------------------------------------------------------------- resources
# A branch of the Lakebase project. `sandbox` is a copy-on-write fork of
# `production`: it inherits the data instantly and shares storage until
# something is written, so experiments here cannot damage what works.
PROJECT_ID  = "bank-churn-prediction"
BRANCH_NAME = "sandbox"

# Two different things that are easy to confuse, so they get different names.
# UC_CATALOG is the Unity Catalog namespace holding the Delta tables.
# PG_SCHEMA is the Postgres schema inside Lakebase holding the operational tables.
UC_CATALOG = "bank_churn_eng"
PG_SCHEMA  = "bank_churn"

PG_DATABASE = "databricks_postgres"
PG_PORT     = 5432

# The source file lives in a Unity Catalog volume. It is read from there rather
# than downloaded at run time: the notebook is reproducible without Kaggle
# credentials, and the sha256 below still proves which exact file was used.
VOLUME_PATH = f"/Volumes/{UC_CATALOG}/bronze/raw_data/churn.csv"
SOURCE_URL  = "https://www.kaggle.com/datasets/mathchi/churn-for-bank-customers"

# ---------------------------------------------------------------- economics
# Six assumptions, fixed in notebook 00 before any model was trained. They are
# assumptions, not data: the dataset contains none of them. They are kept here
# as parameters so that replacing them with the bank's real figures recomputes
# everything downstream instead of requiring edits in six places.
ANNUAL_MARGIN   = 200.0   # EUR per customer per year
HORIZON_YEARS   = 3       # no discounting, to avoid adding another assumption
CONTACT_COST    = 20.0    # EUR, commercial handling and channel
INCENTIVE_COST  = 50.0    # EUR, only paid if the customer accepts
SUCCESS_RATE    = 0.30    # of the leaving customers who get contacted
CAPACITY        = 800     # customers the retention team can call per campaign

CLV = ANNUAL_MARGIN * HORIZON_YEARS                       # 600 EUR

# What contacting one customer is worth, depending on whether they were leaving.
VALUE_TP = SUCCESS_RATE * CLV - CONTACT_COST - SUCCESS_RATE * INCENTIVE_COST   # +145
COST_FP  = CONTACT_COST + SUCCESS_RATE * INCENTIVE_COST                        #  -35

# Where the expected value of a call turns negative:
#   p * VALUE_TP - (1 - p) * COST_FP = 0
BREAK_EVEN    = COST_FP / (VALUE_TP + COST_FP)   # 0.1944
DECISION_UNIT = VALUE_TP + COST_FP               # 180 EUR separates a hit from a miss

RANDOM_STATE = 42   # every random process in the project uses this

# One experiment for the whole project. Defined here rather than inside a
# notebook: when only notebook 04 set it, notebook 05 opened runs against the
# default experiment, which a user cannot write to, and the logging failed with
# a RestException that left an empty run_id behind.
MLFLOW_EXPERIMENT = "bank_churn_eng"


@dataclass
class Context:
    """Everything a notebook needs to start working."""
    spark: object
    w: object
    endpoint: str
    pg_host: str
    pg_user: str
    branch: str = ""
    started: str = field(default_factory=lambda:
                         dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))

    # ------------------------------------------------------------ Lakebase
    def connect(self):
        """A fresh Postgres connection.

        The OAuth credential is generated per call and lives for 60 minutes.
        Generating it every time is cheaper than reasoning about whether the
        one from twenty minutes ago is still valid.
        """
        import pg8000.dbapi
        token = self.w.postgres.generate_database_credential(self.endpoint).token
        return pg8000.dbapi.connect(
            host=self.pg_host, port=PG_PORT, database=PG_DATABASE,
            user=self.pg_user, password=token,
            ssl_context=ssl.create_default_context(),
        )

    def query(self, sql: str, params=None):
        """Run a SELECT against Lakebase and return a pandas DataFrame."""
        import pandas as pd
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)

    def execute(self, sql: str, params=None):
        """Run a statement that writes. Returns the number of affected rows."""
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount


def bootstrap(verbose: bool = True) -> Context:
    """Open the Spark session and the SDK client, and resolve the Lakebase host."""
    from dotenv import load_dotenv
    load_dotenv()

    # The VS Code Databricks extension injects these, and they silently override
    # the profile in .env. Removing them is what makes the profile authoritative.
    for stale in ("DATABRICKS_AUTH_TYPE", "DATABRICKS_METADATA_SERVICE_URL", "DATABRICKS_HOST"):
        os.environ.pop(stale, None)

    from databricks.connect import DatabricksSession
    from databricks.sdk import WorkspaceClient

    profile = os.getenv("DATABRICKS_PROFILE")
    if not profile:
        raise RuntimeError(
            "DATABRICKS_PROFILE is not set. Copy .env.example to .env and fill it in."
        )

    # Both clients take the same profile. Creating either one without it would
    # fall back to whatever the default profile happens to be.
    spark = (DatabricksSession.builder
             .profile(profile)
             .serverless(True)
             .getOrCreate())
    w = WorkspaceClient(profile=profile)

    # Pin the branch by name instead of taking the first one the API returns.
    # With more than one branch that order is not guaranteed, and the wrong
    # pick would silently write to production.
    branches = list(w.postgres.list_branches(f"projects/{PROJECT_ID}"))
    chosen = [b for b in branches if b.name.split("/")[-1] == BRANCH_NAME]
    if not chosen:
        raise RuntimeError(
            f"Branch '{BRANCH_NAME}' does not exist. Available: "
            f"{[b.name.split('/')[-1] for b in branches]}"
        )
    branch = chosen[0].name

    endpoint = next(iter(w.postgres.list_endpoints(branch))).name

    # The host is resolved from the endpoint rather than copied from the UI:
    # a value pasted by hand goes stale the moment the endpoint is recreated.
    ep = w.postgres.get_endpoint(endpoint)

    ctx = Context(
        spark=spark, w=w, endpoint=endpoint, branch=branch,
        pg_host=ep.status.hosts.host,
        pg_user=w.current_user.me().user_name,
    )

    # MLflow does not point at Databricks on its own when the notebook runs
    # through Databricks Connect: without this it silently creates a local
    # ./mlruns with a SQLite store, and the runs never reach the workspace.
    # Setting the registry explicitly also avoids MLflow probing a Spark config
    # that serverless compute does not expose.
    try:
        import logging
        import mlflow
        mlflow.set_tracking_uri("databricks")
        mlflow.set_registry_uri("databricks-uc")

        # MLflow prints one INFO line per run with a full workspace URL:
        #   View run <name> at: https://<workspace>.cloud.databricks.com/ml/...
        # Those lines get saved into the notebook output and would publish the
        # workspace host, the experiment id and every run id to the repository.
        #
        # Setting the parent logger is not enough: MLflow configures its own
        # loggers with propagate=False and attaches a handler at INFO, so the
        # children keep their own level and the handler has to be lowered too.
        # Warnings and errors still come through.
        _quiet = ("mlflow",
                  "mlflow.tracking.fluent",
                  "mlflow.models.model",
                  "mlflow.tracking._tracking_service.client",
                  "mlflow.utils.autologging_utils")
        for _name in _quiet:
            _lg = logging.getLogger(_name)
            _lg.setLevel(logging.WARNING)
            for _h in _lg.handlers:
                _h.setLevel(logging.WARNING)

        # Every notebook logs into the same experiment. Without this, a notebook
        # that only calls start_run() writes to the default experiment, which is
        # not writable, and the run is lost.
        mlflow.set_experiment(f"/Users/{ctx.pg_user}/{MLFLOW_EXPERIMENT}")
    except Exception as exc:                       # noqa: BLE001
        print(f"[warn] could not point MLflow at Databricks ({type(exc).__name__})")

    if verbose:
        print("connected to Databricks")
        print(f"  branch   : {BRANCH_NAME}")
        print(f"  catalog  : {UC_CATALOG}")
        # The user name is an email address, so only the domain-free part is shown.
        print(f"  identity : resolved ({len(ctx.pg_user)} chars, not printed)")

    return ctx


def cost_summary() -> str:
    """One-line reminder of the economics, handy at the top of a notebook."""
    return (f"value(TP)={VALUE_TP:.0f} EUR | cost(FP)={COST_FP:.0f} EUR | "
            f"break-even p*={BREAK_EVEN:.4f} | capacity={CAPACITY}")
