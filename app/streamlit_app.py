"""
Bank customer churn — retention dashboard.

This is the public copy of the application. The one deployed on Databricks Apps
queries the SQL warehouse directly; this one reads the parquet snapshot exported
by notebook 06, so it runs anywhere without credentials.

That difference is deliberate. A dashboard showing ten thousand pre-scored rows
does not need a query engine behind it, and requiring one would mean either
publishing credentials or leaving the page permanently unreachable.

    streamlit run app/streamlit_app.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------- setup
DATA = Path(__file__).resolve().parent.parent / "data"

CHURN, SAFE, ACC = "#a8471f", "#2c5a72", "#8a5a08"
GREY, INK = "#78736a", "#1c1a17"
LEVELS = ["high", "medium", "low"]

# The cost model, fixed in notebook 00 before any model was trained. Repeated
# here rather than imported because the app has to run on Streamlit Cloud with
# nothing from src/ installed. If these ever change, they change in both places.
VALUE_TP = 145.0   # euros recovered when a leaving customer is retained
COST_FP  = 35.0    # euros wasted contacting someone who was staying anyway

st.set_page_config(page_title="Bank churn — retention", layout="wide",
                   initial_sidebar_state="collapsed")


@st.cache_data
def load():
    """Read the snapshot once and keep it in memory across reruns."""
    frames = {}
    for name in ("predictions", "model_metrics", "model_comparison", "feature_importance"):
        path = DATA / f"{name}.parquet"
        frames[name] = pd.read_parquet(path) if path.exists() else None
    manifest = pd.read_json(DATA / "manifest.json").iloc[0] if (DATA / "manifest.json").exists() else None
    return frames, manifest


@st.cache_resource
def load_model():
    """The trained model, if it was exported. The app works without it."""
    path = DATA / "model.joblib"
    if not path.exists():
        return None
    try:
        import joblib
        return joblib.load(path)
    except Exception:
        return None


frames, manifest = load()
df = frames["predictions"]

if df is None:
    st.error("No snapshot found. Run notebook 06 to generate `data/predictions.parquet`.")
    st.stop()

met = frames["model_metrics"].iloc[0] if frames["model_metrics"] is not None else None
CAPACITY = int((df["risk_level"] == "high").sum())


def pct(x):
    return f"{x * 100:.1f}%"


# ------------------------------------------------------------------- layout
st.title("Bank customer churn — retention")
st.caption(
    "The bank can call a limited number of customers per campaign. This ranks the "
    "portfolio so the calls go where they are worth making."
)

tabs = st.tabs(["Executive summary", "Segmentation", "Customers at risk",
                "Model performance", "Individual prediction"])

# =========================================================== 1 · SUMMARY ====
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers analysed", f"{len(df):,}")
    c2.metric("Actual churn rate", pct(df["actual_churn"].mean()))
    c3.metric("High-risk customers", f"{CAPACITY:,}",
              help="Set by campaign capacity, not by a fixed probability cut")
    if met is not None:
        c4.metric("Model ROC-AUC", f"{met['roc_auc']:.4f}")

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        st.subheader("How the portfolio splits")
        split = (df.groupby("risk_level").size().reindex(LEVELS).fillna(0).astype(int))
        fig = px.bar(x=split.index, y=split.values,
                     color=split.index,
                     color_discrete_map={"high": CHURN, "medium": ACC, "low": SAFE},
                     labels={"x": "Risk level", "y": "Customers"}, text=split.values)
        fig.update_traces(textposition="outside")
        fig.update_layout(height=380, showlegend=False, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Model validation")
        check = (df.groupby("risk_level")
                   .agg(customers=("actual_churn", "size"),
                        mean_probability=("churn_probability", lambda s: round(s.mean() * 100, 1)),
                        actual_churn=("actual_churn", lambda s: round(s.mean() * 100, 1)))
                   .reindex(LEVELS))
        check.columns = ["Customers", "Mean probability (%)", "Actual churn (%)"]
        st.dataframe(check, use_container_width=True)
        st.caption(
            "The two right-hand columns track each other at every level: the model "
            "is **calibrated**. Uncalibrated, the first would overstate the second — "
            "and the profitability threshold would stop meaning anything."
        )

# ====================================================== 2 · SEGMENTATION ====
with tabs[1]:
    st.subheader("Segmentation")
    st.caption("Filters apply to all three charts and to the counts above them.")

    f1, f2, f3 = st.columns([2, 2, 1.4])
    countries = f1.multiselect("Country", sorted(df["geography"].unique()),
                               default=sorted(df["geography"].unique()))
    bands = f2.multiselect("Age band", sorted(df["age_group"].unique()),
                           default=sorted(df["age_group"].unique()))
    activity = f3.radio("Activity", ["All", "Active only", "Inactive only"], horizontal=False)

    sub = df[df["geography"].isin(countries) & df["age_group"].isin(bands)]
    if activity == "Active only":
        sub = sub[sub["is_active_member"]]
    elif activity == "Inactive only":
        sub = sub[~sub["is_active_member"]]

    m1, m2, m3 = st.columns(3)
    m1.metric("Customers filtered", f"{len(sub):,}")
    m2.metric("Churn rate", pct(sub["actual_churn"].mean()) if len(sub) else "—")
    m3.metric("High risk", f"{int((sub['risk_level'] == 'high').sum()):,}")

    if len(sub) == 0:
        st.info("No customers match these filters.")
        st.stop()

    st.divider()
    g1, g2 = st.columns(2)

    with g1:
        by_age = (sub.groupby("age_group")["actual_churn"].mean() * 100).round(1)
        fig = px.bar(x=by_age.index, y=by_age.values,
                     labels={"x": "Age band", "y": "% churn"}, text=by_age.values)
        fig.update_traces(marker_color=CHURN, textposition="outside")
        fig.update_layout(height=350, margin=dict(t=30, b=10), title="Churn by age")
        st.plotly_chart(fig, use_container_width=True)

    with g2:
        by_geo = (sub.groupby("geography")["actual_churn"].mean() * 100).round(1).sort_values()
        fig = px.bar(x=by_geo.values, y=by_geo.index, orientation="h",
                     labels={"x": "% churn", "y": "Country"}, text=by_geo.values)
        fig.update_traces(marker_color=CHURN, textposition="outside")
        fig.update_layout(height=350, margin=dict(t=30, b=10), title="Churn by country")
        st.plotly_chart(fig, use_container_width=True)

    cross = (sub.groupby(["age_group", "is_active_member"])["actual_churn"]
                .mean().mul(100).round(1).reset_index())
    cross["Activity"] = np.where(cross["is_active_member"], "Active", "Inactive")
    fig = px.bar(cross, x="age_group", y="actual_churn", color="Activity",
                 barmode="group", text="actual_churn",
                 color_discrete_map={"Active": SAFE, "Inactive": CHURN},
                 labels={"age_group": "Age band", "actual_churn": "% churn"})
    fig.update_traces(textposition="outside")
    fig.update_layout(height=390, margin=dict(t=30, b=10),
                      title="Churn by age and activity")
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "The main finding of the analysis: among **inactive** customers risk keeps "
        "climbing with age, while among active ones it falls again after 60. "
        "Activity is the only variable of the two the bank can act on."
    )

# =================================================== 3 · CUSTOMERS AT RISK ==
with tabs[2]:
    st.subheader("Customers at risk")
    st.caption("Ranked list for the retention campaign. Surnames are not carried.")

    r1, r2, r3 = st.columns([1.2, 1, 2])
    level = r1.selectbox("Risk level", LEVELS, index=0)
    rows = r2.number_input("Rows to show", 10, 1000, 100, step=10)
    where = r3.multiselect("Country", sorted(df["geography"].unique()),
                           default=sorted(df["geography"].unique()), key="risk_country")

    listing = (df[(df["risk_level"] == level) & (df["geography"].isin(where))]
               .sort_values("churn_probability", ascending=False)
               .head(int(rows)))

    st.dataframe(
        listing[["customer_id", "churn_probability", "risk_level", "suggested_action",
                 "geography", "age_group", "is_active_member", "products_group"]]
        .rename(columns={"customer_id": "Customer", "churn_probability": "Probability",
                         "risk_level": "Level", "suggested_action": "Suggested action",
                         "geography": "Country", "age_group": "Age band",
                         "is_active_member": "Active", "products_group": "Products"}),
        use_container_width=True, hide_index=True,
        column_config={"Probability": st.column_config.ProgressColumn(
            "Probability", min_value=0.0, max_value=1.0, format="%.3f")},
    )

    st.download_button("Download as CSV", listing.to_csv(index=False).encode(),
                       file_name=f"customers_{level}_risk.csv", mime="text/csv")

# ================================================== 4 · MODEL PERFORMANCE ===
with tabs[3]:
    st.subheader("Model performance")

    comp = frames["model_comparison"]
    if comp is not None:
        c = comp.sort_values("average_precision")
        fig = px.bar(c, x="average_precision", y="model", orientation="h",
                     color="is_baseline", text_auto=".4f",
                     color_discrete_map={True: GREY, False: CHURN},
                     labels={"average_precision": "Average precision (cross-validated)",
                             "model": "", "is_baseline": "Baseline"})
        fig.update_traces(textposition="inside", insidetextanchor="end")
        fig.update_layout(height=380, margin=dict(t=20, b=10), xaxis=dict(range=[0, 1]))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Grey bars are the baselines. `baseline_business` is a two-variable rule "
            "the bank could apply with no model at all: it is the real rival, and the "
            "comparison that decides whether this project was worth doing."
        )

    st.divider()
    p1, p2 = st.columns(2)

    with p1:
        st.subheader("Confusion matrix, in euros")
        if met is not None:
            tn, fp = int(met["tn"]), int(met["fp"])
            fn, tp = int(met["fn"]), int(met["tp"])
            z = [[tn, fp], [fn, tp]]

            # The four cells are not equivalent, and the whole project rests on
            # that. Showing counts alone hides the asymmetry: one false positive
            # costs 35 EUR, one true positive recovers 145.
            text = [
                [f"TN<br><b>{tn:,}</b><br>no cost",
                 f"FP<br><b>{fp:,}</b><br>{-fp * COST_FP:+,.0f} €"],
                [f"FN<br><b>{fn:,}</b><br>{-fn * VALUE_TP:+,.0f} € not recovered",
                 f"TP<br><b>{tp:,}</b><br>{tp * VALUE_TP:+,.0f} €"],
            ]
            fig = go.Figure(go.Heatmap(
                z=z, text=text, texttemplate="%{text}", colorscale="Oranges",
                showscale=False,
                x=["predicted: stays", "predicted: leaves"],
                y=["actual: stays", "actual: leaves"]))
            fig.update_layout(height=330, margin=dict(t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

            campaign = tp * VALUE_TP - fp * COST_FP
            v1, v2, v3 = st.columns(3)
            v1.metric("Campaign value", f"{campaign:+,.0f} €",
                      help=f"{tp} recovered × {VALUE_TP:.0f} € − {fp} wasted calls × {COST_FP:.0f} €")
            v2.metric("Value per call", f"{campaign / max(tp + fp, 1):+,.0f} €")
            v3.metric("Cost of a wrong call", f"−{COST_FP:.0f} €",
                      help="Against +145 € for a right one: the 180 € gap is the unit of this work")

            st.caption(
                f"On the test set, at threshold {met['threshold']:.3f}. The FN cell "
                "shows what was **not** recovered, not money spent — most of those "
                "are the consequence of a fixed quota, not of the model being wrong."
            )

    with p2:
        st.subheader("Most influential variables")
        fi = frames["feature_importance"]
        if fi is not None:
            f = fi.sort_values("importance")
            fig = px.bar(f, x="importance", y="feature", orientation="h",
                         error_x="std", color="distinguishable",
                         color_discrete_map={True: CHURN, False: GREY},
                         labels={"importance": "Drop in average precision when shuffled",
                                 "feature": "", "distinguishable": "Real effect"})
            fig.update_layout(height=330, margin=dict(t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Permutation importance on unseen data. In grey, variables whose "
                "effect is smaller than their own error — indistinguishable from zero."
            )

    st.divider()
    st.subheader("Technical sheet")
    if met is not None:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("ROC-AUC", f"{met['roc_auc']:.4f}")
        s2.metric("Average precision", f"{met['average_precision']:.4f}")
        s3.metric("Brier score", f"{met['brier']:.4f}",
                  help="Calibration quality. Lower is better")
        s4.metric("Precision", f"{met['precision']:.4f}")

        st.markdown(f"""
- **Model:** {met['model']} without `gender`, calibrated isotonically.
- **Why without gender:** its measured contribution was negligible. That does not
  justify using a protected characteristic to allocate a benefit — especially one
  that predicts well only because it stands in for something never measured.
- **Threshold:** {met['threshold']:.4f}, set by operating capacity and validated
  against the profitability threshold ({met['cost_threshold']:.4f}).
- **Known ceiling:** recall cannot exceed {met['recall_ceiling']:.1%} with this
  capacity, however good the model is. It reaches **{met['pct_of_ceiling']:.1%}**
  of that maximum.
- **Known limit:** it detects churn well among older and inactive customers, and
  misses it among younger ones.
""")

# ================================================ 5 · INDIVIDUAL PREDICTION =
# Reference values come from the exploratory analysis, not from intuition. Every
# figure below was measured before any model was trained, which is what makes
# this tab a test of the model rather than a demonstration of the interface.
FIELDS = [
    ("Age", "18 – 92",
     "Peak of 56% churn at 50-59. Not linear, and what happens after 60 depends "
     "on activity.", "Strong"),
    ("Products held", "1 – 4",
     "1 → 27.7% · 2 → 7.6% · 3 → 82.7% · 4 → 100%. Two protects, three or four fire.",
     "Strongest"),
    ("Active member", "yes / no",
     "Inactive 26.9% vs active 14.3%. The gap grows with age: 4 points at 25, "
     "73 points past 60.", "Strong"),
    ("Country", "France · Germany · Spain",
     "Germany 32.4% against roughly 16% for the other two, with no observable "
     "variable explaining it.", "Moderate"),
    ("Balance", "0 – 250,898",
     "Zero balance 13.8% vs positive 18.7%. Zero is a distinct state, not a "
     "missing value.", "Slight"),
    ("Credit score", "350 – 850",
     "Five bands between 18.6% and 22.0%, in no order. Spearman −0.023.", "None"),
    ("Tenure", "0 – 10 years",
     "Eleven values all around 20%. Chi-squared does not reject independence.", "None"),
    ("Estimated salary", "12 – 199,992",
     "Uniformly distributed, Spearman +0.012. Predicted to be noise before it "
     "was measured.", "None"),
    ("Has a credit card", "yes / no",
     "20.8% against 20.2%. No difference.", "None"),
]

# Eight profiles with the outcome the analysis leads you to expect. The last two
# are identical except for one checkbox: that pair is the point of the section.
PROFILES = {
    "Inactive, over 60, Germany": dict(
        age=64, credit_score=620, tenure=4, balance=120000.0, products=1,
        salary=95000.0, country="Germany", active=False, card=True,
        expect="high", why="Every strong signal aligned: the highest-risk cell in "
                           "the whole dataset is inactive and over 60."),
    "Four products": dict(
        age=45, credit_score=700, tenure=5, balance=80000.0, products=4,
        salary=100000.0, country="France", active=True, card=True,
        expect="high", why="All sixty customers with four products left. The model "
                           "learned a deterministic rule, and it should fire even "
                           "with everything else looking safe."),
    "Three products, inactive": dict(
        age=38, credit_score=680, tenure=3, balance=95000.0, products=3,
        salary=85000.0, country="Germany", active=False, card=True,
        expect="high", why="Three or more products churns at 82.7%, and inactivity "
                           "adds to it."),
    "50-59, inactive, France": dict(
        age=55, credit_score=640, tenure=7, balance=110000.0, products=1,
        salary=60000.0, country="France", active=False, card=False,
        expect="high", why="The age peak combined with inactivity."),
    "40s, one product, active": dict(
        age=44, credit_score=710, tenure=6, balance=90000.0, products=1,
        salary=120000.0, country="Spain", active=True, card=True,
        expect="medium", why="One product raises risk, activity pulls it back down. "
                             "Above break-even, below the campaign quota."),
    "Two products, active, young": dict(
        age=29, credit_score=600, tenure=2, balance=0.0, products=2,
        salary=45000.0, country="France", active=True, card=True,
        expect="low", why="Two products is the protective combination, and every "
                          "other signal points the same way."),
    "68, active  (demo A)": dict(
        age=68, credit_score=660, tenure=6, balance=100000.0, products=2,
        salary=70000.0, country="France", active=True, card=True,
        expect="low", why="Intuition says older means riskier. The data disagrees: "
                          "active customers over 60 churn at 12.5%, less than a "
                          "forty-year-old."),
    "68, inactive  (demo B)": dict(
        age=68, credit_score=660, tenure=6, balance=100000.0, products=2,
        salary=70000.0, country="France", active=False, card=True,
        expect="high", why="Identical to demo A except for one checkbox. If both "
                          "come out similar, the model did not capture the "
                          "age × activity interaction and something is wrong."),
}

with tabs[4]:
    st.subheader("Individual prediction")
    model = load_model()

    guide, scorer = st.tabs(["What each field means", "Score a customer"])

    # -------------------------------------------------------------- guide --
    with guide:
        st.caption(
            "Reference measured during the exploratory analysis, before any model "
            "was trained. The right-hand column is what makes this tab a test: four "
            "of these nine fields should barely move the result."
        )
        st.dataframe(
            pd.DataFrame(FIELDS, columns=["Field", "Valid range",
                                          "What the data shows", "Effect"]),
            use_container_width=True, hide_index=True)

        st.markdown("""
**Demonstration 1 — the age × activity interaction.** Load *68, active* and then
*68, inactive*. They differ in one checkbox and should land at opposite ends. This
is the central finding of the project, checkable live.

**Demonstration 2 — the variables that carry no signal.** Take any profile and
move `credit_score` from 350 to 850, or `estimated_salary` from 12 to 199,000. The
probability barely shifts. That is not a defect: those variables have no signal,
and that was established separately before anything was trained.
""")

        st.info(
            "The form does **not** ask for gender. The deployed model does not use "
            "it: its measured contribution did not justify allocating a benefit on "
            "a protected characteristic."
        )

    # ------------------------------------------------------------- scorer --
    with scorer:
        if "profile" not in st.session_state:
            st.session_state.profile = PROFILES["Two products, active, young"]

        st.write("**Load a profile**")
        cols = st.columns(4)
        for i, (name, preset) in enumerate(PROFILES.items()):
            if cols[i % 4].button(name, use_container_width=True, key=f"p{i}"):
                st.session_state.profile = preset
                st.rerun()

        p = st.session_state.profile
        if p.get("why"):
            st.caption(f"**Expected: {p['expect']} risk.** {p['why']}")

        st.divider()

        with st.form("prediction"):
            c1, c2, c3 = st.columns(3)
            age = c1.number_input("Age", 18, 95, p["age"])
            credit_score = c1.number_input("Credit score", 350, 850, p["credit_score"])
            tenure = c2.number_input("Tenure (years)", 0, 10, p["tenure"])
            balance = c2.number_input("Balance", 0.0, 260000.0, p["balance"], step=1000.0)
            products = c3.selectbox("Products held", [1, 2, 3, 4],
                                    index=[1, 2, 3, 4].index(p["products"]))
            salary = c3.number_input("Estimated salary", 0.0, 200000.0, p["salary"],
                                     step=1000.0)

            c4, c5, c6 = st.columns(3)
            country = c4.selectbox("Country", ["France", "Germany", "Spain"],
                                   index=["France", "Germany", "Spain"].index(p["country"]))
            active = c5.checkbox("Active member", value=p["active"])
            has_card = c6.checkbox("Has a credit card", value=p["card"])

            submitted = st.form_submit_button("Score this customer",
                                              use_container_width=True)

        if model is None:
            st.warning(
                "**The trained model is not part of this snapshot, so the form "
                "cannot be scored here.**\n\n"
                "The copy deployed on Databricks loads it from Unity Catalog. This "
                "public version reads pre-scored results, which is what lets the "
                "other four sections work with no credentials at all. To enable "
                "this tab locally, export the model to `data/model.joblib` from "
                "notebook 06."
            )
        elif submitted:
            row = pd.DataFrame([{
                "geography": country, "credit_score": float(credit_score),
                "balance": float(balance), "tenure": float(tenure),
                "estimated_salary": float(salary), "age": float(age),
                "num_of_products": float(products),
                "balance_zero": int(balance == 0),
                "is_active_member": int(active), "has_cr_card": int(has_card),
            }])

            prob = float(model.predict_proba(row)[:, 1][0])
            hi = float(met["threshold"]) if met is not None else 0.5
            lo = float(met["cost_threshold"]) if met is not None else 0.194
            level = "high" if prob >= hi else "medium" if prob >= lo else "low"

            a, b, c = st.columns(3)
            a.metric("Churn probability", f"{prob:.1%}")
            b.metric("Classification", "Leaves" if prob >= hi else "Stays")
            c.metric("Risk level", level.upper(),
                     delta="as expected" if level == p.get("expect") else "differs",
                     delta_color="normal" if level == p.get("expect") else "inverse")

            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=prob * 100, number={"suffix": "%"},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": CHURN},
                       "steps": [{"range": [0, lo * 100], "color": "#e8e4da"},
                                 {"range": [lo * 100, hi * 100], "color": "#f0d9c8"},
                                 {"range": [hi * 100, 100], "color": "#e5b79a"}],
                       "threshold": {"line": {"color": INK, "width": 3},
                                     "value": hi * 100}}))
            fig.update_layout(height=280, margin=dict(t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                f"Grey up to {lo:.1%}: below break-even, calling destroys value. "
                f"Amber up to {hi:.1%}: worth calling but outside the quota. "
                f"Above that: enters the campaign."
            )

            if level == "high":
                st.error("**Suggested action:** " + (
                    "Priority reactivation: phone contact with a usage incentive"
                    if not active else
                    "Portfolio review: audit the combination of products held"
                    if products >= 3 else
                    "Loyalty: commercial contact and review of terms"))
            elif level == "medium":
                st.warning("**Suggested action:** watch. Include if campaign budget remains.")
            else:
                st.success("**Suggested action:** none. This customer is not at risk.")

# ------------------------------------------------------------------ footer
st.divider()
if manifest is not None:
    st.caption(
        f"Model {manifest['model_name']} {manifest['model_version']} · "
        f"snapshot generated {str(manifest['generated_at'])[:10]} · "
        f"capacity {manifest['capacity']} contacts per campaign"
    )
