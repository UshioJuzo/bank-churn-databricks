# Website source

Quarto source for the project site.

## Structure

```
site/
├── _quarto.yml     project config, navbar, theme
├── index.qmd       Overview
├── findings.qmd    What the data said
├── pipeline.qmd    Architecture and the reverse ETL
├── model.qmd       Model selection, calibration, the two failed criteria
├── app.qmd         The dashboard
├── charts.py       every figure, drawn from ../data/
└── theme/
    ├── PALETA.md         the palette and how roles are assigned
    ├── _base.scss        structure and components, no colours
    ├── tema-oscuro.scss  dark palette, the default
    └── tema-claro.scss   light palette, the toggle alternative
```

## Why the figures read from `../data/`

The site could query Databricks directly, but then it would only render on a
machine holding credentials, and every build would depend on a warehouse being
awake. `data/` holds a few hundred kilobytes of parquet exported by notebook 06,
so the site renders in seconds anywhere.

The aggregates come from the **full** portfolio, not a sample. Nothing on the
site is approximate.

## Rendering

```bash
cd site
quarto render
```

Output goes to `../docs/`, which is what GitHub Pages serves.

Figures are matplotlib rasters on a cream background rather than interactive
charts. A raster does not change when the reader toggles dark and light mode, so
it has to work against both — which is why the palette uses the middle of the
range rather than the extremes. That reasoning is in `theme/PALETA.md`.

## Requirements

```bash
pip install pandas pyarrow matplotlib tabulate jupyter
```

Plus [Quarto](https://quarto.org/docs/get-started/) itself.
