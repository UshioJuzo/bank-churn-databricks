"""
charts.py — every figure on the site, drawn from the parquet snapshot.

Same rule as the flights site: if a function *is* the subject of a section, it
is shown there in full; if it is scaffolding, it lives only here.

Figures are matplotlib rasters on a cream background rather than interactive
Plotly. A raster does not change when the reader toggles dark and light mode, so
it has to work against both — which is why the palette uses the middle of the
range rather than the extremes. That reasoning is in theme/PALETA.md.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

# Mirror of the theme palette for matplotlib. If theme/PALETA.md changes, this
# has to change with it.
INK, PAPER = "#042728", "#ffffde"
RUST, RUST_LIGHT, SAND = "#913d1a", "#d77b30", "#fdd08e"
TEAL, STEEL, MINT = "#389e9c", "#20767c", "#b3e0cc"
GREY = "#7a7259"

LEVELS = ["high", "medium", "low"]

# Every chart function ends with plt.show() and returns nothing, on purpose.
# The inline backend displays any figure created during a cell, and if the
# function ALSO returned the Figure the expression hook would render it a second
# time -- two identical images per chunk. Returning None leaves exactly one.


def apply_style():
    plt.rcParams.update({
        "figure.dpi": 130,
        "figure.facecolor": PAPER,
        "axes.facecolor": PAPER,
        "savefig.facecolor": PAPER,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.grid": True,
        "grid.alpha": 0.18,
        "grid.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 9.5,
        "figure.figsize": (8, 4.2),
    })


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


def manifest() -> dict:
    return pd.read_json(DATA / "manifest.json").iloc[0].to_dict()


# ------------------------------------------------------------------ figures
def portfolio_split():
    """How the 10,000 customers fall across the three risk levels."""
    apply_style()
    df = load("predictions")
    split = df.groupby("risk_level").size().reindex(LEVELS)

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    colours = [RUST, RUST_LIGHT, TEAL]
    bars = ax.bar(range(3), split.values, color=colours, width=0.6)
    for b, v in zip(bars, split.values):
        ax.text(b.get_x() + b.get_width() / 2, v + 90, f"{v:,}",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["high\n(the campaign)", "medium\n(watch)", "low\n(no action)"])
    ax.set_ylabel("customers")
    ax.set_ylim(0, split.max() * 1.16)
    fig.tight_layout()
    plt.show()


def calibration_by_level():
    """Predicted probability against observed churn, per risk level."""
    apply_style()
    df = load("predictions")
    t = (df.groupby("risk_level")
           .agg(predicted=("churn_probability", "mean"),
                observed=("actual_churn", "mean"))
           .reindex(LEVELS) * 100)

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    x = np.arange(3)
    ax.bar(x - 0.19, t["predicted"], width=0.36, color=STEEL, label="mean predicted")
    ax.bar(x + 0.19, t["observed"],  width=0.36, color=RUST,  label="observed churn")
    for i, (p, o) in enumerate(zip(t["predicted"], t["observed"])):
        ax.text(i - 0.19, p + 1.4, f"{p:.1f}%", ha="center", fontsize=8.5)
        ax.text(i + 0.19, o + 1.4, f"{o:.1f}%", ha="center", fontsize=8.5)
    ax.set_xticks(x); ax.set_xticklabels(LEVELS)
    ax.set_ylabel("%"); ax.set_ylim(0, 105)
    ax.legend(fontsize=8.5, frameon=False)
    fig.tight_layout()
    plt.show()


def model_comparison():
    """Average precision, models against baselines."""
    apply_style()
    c = load("model_comparison").sort_values("average_precision")

    fig, ax = plt.subplots(figsize=(8, 3.8))
    colours = [GREY if b else RUST for b in c["is_baseline"]]
    ax.barh(range(len(c)), c["average_precision"], color=colours, height=0.62)
    for i, v in enumerate(c["average_precision"]):
        ax.text(v + 0.008, i, f"{v:.4f}", va="center", fontsize=8.5)
    ax.set_yticks(range(len(c)))
    ax.set_yticklabels(c["model"], fontsize=8.5)
    ax.set_xlabel("average precision (cross-validated)")
    ax.set_xlim(0, 0.82)
    fig.tight_layout()
    plt.show()


def feature_importance():
    """Permutation importance with its error bars."""
    apply_style()
    f = load("feature_importance").sort_values("importance")

    fig, ax = plt.subplots(figsize=(8, 4))
    colours = [RUST if d else GREY for d in f["distinguishable"]]
    ax.barh(range(len(f)), f["importance"], xerr=f["std"], color=colours,
            height=0.62, error_kw=dict(ecolor=INK, lw=0.9, capsize=2.5))
    ax.set_yticks(range(len(f)))
    ax.set_yticklabels(f["feature"], fontsize=8.5)
    ax.set_xlabel("drop in average precision when the column is shuffled")
    fig.tight_layout()
    plt.show()


def confusion_matrix():
    """The four numbers, read in euros."""
    apply_style()
    m = load("model_metrics").iloc[0]
    z = np.array([[int(m.tn), int(m.fp)], [int(m.fn), int(m.tp)]])

    fig, ax = plt.subplots(figsize=(5.4, 4))
    ax.imshow(z, cmap="YlOrBr", aspect="auto")
    labels = [[f"TN\n{z[0,0]:,}\nno cost", f"FP\n{z[0,1]:,}\n−35 € each"],
              [f"FN\n{z[1,0]:,}\nopportunity lost", f"TP\n{z[1,1]:,}\n+145 € each"]]
    for i in range(2):
        for j in range(2):
            ax.text(j, i, labels[i][j], ha="center", va="center", fontsize=9,
                    color="white" if z[i, j] > z.max() * 0.55 else INK)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["predicted: stays", "predicted: leaves"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["actual: stays", "actual: leaves"])
    ax.grid(False)
    fig.tight_layout()
    plt.show()


def age_activity():
    """The interaction: churn by age band, split by activity."""
    apply_style()
    df = load("predictions")
    order = ["18-29", "30-39", "40-49", "50-59", "60+"]
    piv = (df.pivot_table(index="age_group", columns="is_active_member",
                          values="actual_churn", aggfunc="mean")
             .reindex(order) * 100)
    piv.columns = ["inactive", "active"]

    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(order))
    ax.plot(x, piv["inactive"], "o-", color=RUST, lw=2.3, ms=7, label="inactive")
    ax.plot(x, piv["active"],   "o-", color=STEEL, lw=2.3, ms=7, label="active")
    base = df["actual_churn"].mean() * 100
    ax.axhline(base, ls="--", lw=1.1, color=GREY)
    ax.text(0.01, base + 1.5, f"base rate {base:.1f}%", fontsize=8, color=INK,
            transform=ax.get_yaxis_transform())
    for i, (a, b) in enumerate(zip(piv["inactive"], piv["active"])):
        ax.annotate("", xy=(i, a), xytext=(i, b),
                    arrowprops=dict(arrowstyle="<->", color=GREY, lw=0.8, alpha=0.65))
        ax.text(i + 0.07, (a + b) / 2, f"{a-b:.0f} pp", fontsize=7.5, va="center")
    ax.set_xticks(x); ax.set_xticklabels(order)
    ax.set_ylabel("% churn"); ax.set_xlabel("age band")
    ax.legend(fontsize=8.5, frameon=False)
    fig.tight_layout()
    plt.show()


def country_quota():
    """How the 800 contacts were split across countries."""
    apply_style()
    df = load("predictions")
    t = (df.groupby("geography")
           .agg(customers=("actual_churn", "size"),
                churn=("actual_churn", "mean"),
                quota=("risk_level", lambda s: (s == "high").sum())))

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.4))
    a1.bar(t.index, t["churn"] * 100, color=RUST, width=0.55)
    for i, v in enumerate(t["churn"] * 100):
        a1.text(i, v + 0.7, f"{v:.1f}%", ha="center", fontsize=9)
    a1.set_ylabel("% churn"); a1.set_title("Churn rate", fontsize=10, loc="left")
    a1.set_ylim(0, (t["churn"] * 100).max() * 1.2)

    a2.bar(t.index, t["quota"], color=STEEL, width=0.55)
    for i, v in enumerate(t["quota"]):
        a2.text(i, v + 8, f"{v}", ha="center", fontsize=9)
    a2.set_ylabel("contacts"); a2.set_title("Share of the 800 contacts",
                                            fontsize=10, loc="left")
    a2.set_ylim(0, t["quota"].max() * 1.2)
    fig.tight_layout()
    plt.show()


def recall_ceiling():
    """Why the recall criterion was impossible."""
    apply_style()
    m = load("model_metrics").iloc[0]
    ceiling, achieved, target = float(m.recall_ceiling), float(m.recall), 0.60

    fig, ax = plt.subplots(figsize=(8, 2.5))
    ax.barh([0], [1.0], color=SAND, height=0.5, label="all churners")
    ax.barh([0], [ceiling], color=RUST_LIGHT, height=0.5,
            label=f"reachable ceiling ({ceiling:.1%})")
    ax.barh([0], [achieved], color=RUST, height=0.5,
            label=f"model reached ({achieved:.1%})")
    ax.axvline(target, color=INK, lw=2, ls="--")
    ax.text(target + 0.008, 0.32, f"criterion {target:.0%}", fontsize=9, color=INK)
    ax.set_yticks([]); ax.set_xlim(0, 1)
    ax.set_xlabel("share of leaving customers")
    ax.legend(fontsize=8, frameon=False, loc="lower right", ncol=3)
    fig.tight_layout()
    plt.show()
