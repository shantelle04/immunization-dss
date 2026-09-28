"""EDA figures F-D1 to F-D8 and dataset description table T-5.1 for a validated synthetic run.

Figures that read truth/ or imports/ are evaluation material only; the application never loads those folders.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.dates import ConciseDateFormatter, MonthLocator  # noqa: E402

from .sim.config import parse_config  # noqa: E402

# Categorical slots 1 to 4 of the validated reference palette (light mode, CVD-checked).
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
STOCKOUT_FILL, DISRUPTION_FILL = "#f6d3d2", "#dcdbd6"
WIDTH_IN = 6.3
DEMAND_WEEKS = 104

LEVELS = {
    "dispensary": "Dispensary",
    "health_centre": "Health centre",
    "sub_county_hospital": "Sub-county hospital",
}
INDICATOR_LABELS = {"bcg": "BCG", "ipv": "IPV", "zero_dose": "Zero-dose"}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.edgecolor": INK_2,
            "axes.labelcolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "legend.frameon": False,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "figure.facecolor": "white",
        }
    )


def _label(indicator: str) -> str:
    if indicator in INDICATOR_LABELS:
        return INDICATOR_LABELS[indicator]
    for prefix in ("penta", "rota"):
        if indicator.startswith(prefix):
            return prefix.capitalize() + indicator[len(prefix) :]
    return indicator.upper()


def _md_table(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join(lines)


class RunData:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.cfg = parse_config(json.loads((run_dir / "params.json").read_text()))
        self.manifest = json.loads((run_dir / "manifest.json").read_text())
        self.report = json.loads((run_dir / "validation_report.json").read_text())
        if not self.report["passed"]:
            raise ValueError(f"{run_dir.name} did not pass validate-sim; EDA needs a validated run")

    def csv(self, rel: str) -> pd.DataFrame:
        return pd.read_csv(self.run_dir / rel, keep_default_na=False, low_memory=False)


def _dumbbell(ax, labels: list[str], sim: list[float], ref: list[float]) -> None:
    y = np.arange(len(labels))[::-1]
    for yi, s, r in zip(y, sim, ref, strict=True):
        ax.plot([r, s], [yi, yi], color=GRID, linewidth=2, zorder=1)
        ax.annotate(f"{s - r:+.1f}", (max(s, r) + 0.6, yi), va="center", fontsize=7.5, color=INK_2)
    ax.scatter(ref, y, s=42, facecolors="white", edgecolors=INK_2, linewidths=1.4, label="KDHS 2022")
    ax.scatter(sim, y, s=42, color=BLUE, marker="D", label="Simulated (seed run)", zorder=3)
    ax.set_yticks(y, labels)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Children vaccinated (%)")
    ax.legend(loc="lower left", ncols=2, bbox_to_anchor=(0, 1.0))


def fig_calibration(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    cov = pd.DataFrame(d.report["tables"]["coverage_vs_kdhs2022"])
    doses = cov[cov.indicator != "zero_dose"]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.6))
    _dumbbell(ax, [_label(i) for i in doses.indicator], list(doses.simulated_pct), list(doses.kdhs_2022_pct))
    ax.set_xlim(60, 102)
    fig.savefig(out / "F-D1_calibration_vs_kdhs2022.png")
    plt.close(fig)
    table = cov.assign(indicator=cov.indicator.map(_label))
    return "F-D1_calibration_vs_kdhs2022.png", table


def fig_subgroups(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    sub = pd.DataFrame(d.report["tables"]["penta3_by_group"])
    groups = zip(sub.group, sub.category, strict=True)
    labels = [f"{g.replace('_', ' ').capitalize()}: {c}" for g, c in groups]
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 4.0))
    _dumbbell(ax, labels, list(sub.simulated_penta3_pct), list(sub.kdhs_2022_pct))
    ax.set_xlim(60, 102)
    ax.set_xlabel("Children aged 12 to 23 months with Penta3 (%)")
    fig.savefig(out / "F-D8_penta3_by_subgroup.png")
    plt.close(fig)
    sub = sub.assign(difference_pp=(sub.simulated_penta3_pct - sub.kdhs_2022_pct).round(1))
    return "F-D8_penta3_by_subgroup.png", sub


def _app_cohort_doses(d: RunData) -> tuple[pd.DataFrame, pd.DataFrame]:
    children = d.csv("app/children.csv")
    events = d.csv("app/immunization_events.csv")
    facilities = d.csv("app/facilities.csv")
    as_of = pd.Timestamp(d.cfg.as_of_date)
    children["age_days"] = (as_of - pd.to_datetime(children.date_of_birth)).dt.days
    children = children.merge(
        facilities[["facility_code", "keph_level"]],
        left_on="registration_facility_code",
        right_on="facility_code",
    )
    events = events[pd.to_datetime(events.given_on) < as_of]
    return children, events


def fig_dropout(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    children, events = _app_cohort_doses(d)
    cohort = children[(children.age_days >= 365) & (children.age_days < 730)]
    has = {dose: set(events.child_id[events.dose_code == dose]) for dose in ("PENTA-1", "PENTA-3", "MR-1")}
    rows = []
    for level, label in [*LEVELS.items(), ("all", "All facilities")]:
        members = cohort if level == "all" else cohort[cohort.keph_level == level]
        n1, n3, nm = (members.child_id.isin(has[k]).sum() for k in ("PENTA-1", "PENTA-3", "MR-1"))
        rows.append(
            {
                "facility_level": label,
                "registered_12_23m": len(members),
                "penta1": int(n1),
                "penta3": int(n3),
                "mr1": int(nm),
                "dropout_penta1_penta3_pct": round(100 * (n1 - n3) / n1, 1),
                "dropout_penta1_mr1_pct": round(100 * (n1 - nm) / n1, 1),
            }
        )
    table = pd.DataFrame(rows)
    x = np.arange(len(table))
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.2))
    for offset, col, color, hatch, name in [
        (-0.19, "dropout_penta1_penta3_pct", BLUE, None, "Penta1 to Penta3"),
        (0.19, "dropout_penta1_mr1_pct", ORANGE, "////", "Penta1 to MR1"),
    ]:
        bars = ax.bar(
            x + offset, table[col], width=0.36, color=color, hatch=hatch, edgecolor="white", label=name
        )
        ax.bar_label(bars, fmt="%.1f", fontsize=7.5, color=INK_2, padding=2)
    ax.set_xticks(x, table.facility_level)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Dropout (%)")
    ax.legend(loc="upper left", ncols=2, bbox_to_anchor=(0, 1.12))
    fig.savefig(out / "F-D2_dropout_by_level.png")
    plt.close(fig)
    return "F-D2_dropout_by_level.png", table


def fig_timeliness(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    children, events = _app_cohort_doses(d)
    schedule = d.csv("app/schedule.csv").set_index("dose_code")
    dob = children.set_index("child_id").date_of_birth
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.4))
    rows = []
    styles = [(BLUE, "-"), (ORANGE, "--"), (AQUA, "-."), (YELLOW, ":")]
    for (dose, name), (color, ls) in zip(
        [("BCG-1", "BCG"), ("PENTA-1", "Penta1"), ("PENTA-3", "Penta3"), ("MR-1", "MR1")], styles, strict=True
    ):
        ev = events[events.dose_code == dose]
        age = (
            (pd.to_datetime(ev.given_on).values - pd.to_datetime(dob.loc[ev.child_id]).values)
            .astype("timedelta64[D]")
            .astype(int)
        )
        delay = np.sort(age - int(schedule.loc[dose, "recommended_age_days"]))
        share = np.arange(1, len(delay) + 1) / len(delay) * 100
        ax.step(delay, share, where="post", color=color, linestyle=ls, linewidth=2, label=name)
        rows.append(
            {
                "dose": name,
                "doses_given": len(delay),
                "median_days_late": float(np.median(delay)),
                "p75_days_late": float(np.percentile(delay, 75)),
                "p90_days_late": float(np.percentile(delay, 90)),
                "within_28_days_pct": round(100 * float((delay <= 28).mean()), 1),
            }
        )
    ax.axvline(28, color=INK_2, linestyle=(0, (2, 2)), linewidth=1)
    ax.annotate("28 days", (28, 5), xytext=(3, 0), textcoords="offset points", color=INK_2, fontsize=7.5)
    ax.set_xlim(-5, 180)
    ax.set_ylim(0, 101)
    ax.set_xlabel("Days after the recommended age")
    ax.set_ylabel("Doses given by then (%)")
    ax.legend(loc="lower right")
    fig.savefig(out / "F-D3_timeliness.png")
    plt.close(fig)
    return "F-D3_timeliness.png", pd.DataFrame(rows)


def _shade_weeks(ax, weeks: pd.Series, color: str) -> None:
    for week in weeks:
        start = week.to_pydatetime()
        ax.axvspan(start, start + dt.timedelta(days=7), color=color, linewidth=0, zorder=0)


def _weekly(d: RunData) -> pd.DataFrame:
    w = d.csv("truth/weekly_stock.csv")
    w["week_start"] = pd.to_datetime(w.week_start)
    w["stockout"] = w.stockout.astype(str) == "True"
    w["in_disruption"] = w.in_disruption.astype(str) == "True"
    return w[w.week_start >= pd.Timestamp(d.cfg.start_date)]


def fig_weekly_demand(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    w = _weekly(d)
    w = w[w.week_start > w.week_start.max() - dt.timedelta(weeks=DEMAND_WEEKS)]
    antigens = ["PENTA", "MR"]
    so = w[w.antigen_code.isin(antigens)].groupby("facility_code").stockout.sum()
    picks = [so[so.index.str.startswith(p)].idxmax() for p in ("SYN-D", "SYN-S")]
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH_IN, 4.8), sharex=True)
    rows = []
    for r, fac in enumerate(picks):
        for c, ag in enumerate(antigens):
            ax = axes[r, c]
            s = w[(w.facility_code == fac) & (w.antigen_code == ag)]
            _shade_weeks(ax, s.week_start[s.stockout], STOCKOUT_FILL)
            ax.plot(s.week_start, s.requested_doses, color=ORANGE, linestyle="--", linewidth=1.2)
            ax.plot(s.week_start, s.administered_doses, color=BLUE, linewidth=1.2)
            ax.set_title(f"{fac}, {'Penta' if ag == 'PENTA' else ag}", fontsize=9, loc="left", color=INK)
            rows.append(
                {
                    "facility": fac,
                    "antigen": ag,
                    "weeks": len(s),
                    "stockout_weeks": int(s.stockout.sum()),
                    "requested_doses": int(s.requested_doses.sum()),
                    "administered_doses": int(s.administered_doses.sum()),
                    "unmet_doses": int(s.unmet_doses.sum()),
                }
            )
        axes[r, 0].set_ylabel("Doses per week")
    locator = MonthLocator(bymonth=(1, 7))
    for ax in axes[1]:
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
    handles = [
        plt.Line2D([], [], color=BLUE, linewidth=1.5, label="Administered (what the system records)"),
        plt.Line2D([], [], color=ORANGE, linestyle="--", linewidth=1.5, label="True demand (ground truth)"),
        plt.Rectangle((0, 0), 1, 1, color=STOCKOUT_FILL, label="Stock-out week"),
    ]
    fig.legend(handles=handles, loc="upper left", ncols=3, bbox_to_anchor=(0.02, 1.04), fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "F-D4_weekly_demand_stockouts.png")
    plt.close(fig)
    return "F-D4_weekly_demand_stockouts.png", pd.DataFrame(rows)


def fig_stock_levels(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    w = _weekly(d)
    min_weeks = float(d.cfg.section("stock")["min_stock_weeks"])
    fac = (
        w[(w.antigen_code.isin(["OPV", "MR"])) & w.facility_code.str.startswith("SYN-H")]
        .groupby("facility_code")
        .stockout.sum()
        .idxmax()
    )
    fig, axes = plt.subplots(2, 1, figsize=(WIDTH_IN, 4.4), sharex=True)
    rows = []
    for ax, ag in zip(axes, ["OPV", "MR"], strict=True):
        s = w[(w.facility_code == fac) & (w.antigen_code == ag)].sort_values("week_start")
        use = (s.administered_doses + s.wastage_doses).shift(1).rolling(12, min_periods=4).mean()
        minimum = min_weeks * use
        _shade_weeks(ax, s.week_start[s.in_disruption], DISRUPTION_FILL)
        _shade_weeks(ax, s.week_start[s.stockout], STOCKOUT_FILL)
        ax.plot(s.week_start, s.closing_doses, color=BLUE, linewidth=1.2)
        ax.plot(s.week_start, minimum, color=INK_2, linestyle=(0, (3, 2)), linewidth=1)
        ax.set_title(f"{fac}, {ag}", fontsize=9, loc="left", color=INK)
        ax.set_ylabel("Doses in stock")
        rows.append(
            {
                "facility": fac,
                "antigen": ag,
                "weeks_below_minimum": int((s.closing_doses < minimum).sum()),
                "stockout_weeks": int(s.stockout.sum()),
                "disruption_weeks": int(s.in_disruption.sum()),
                "median_closing_doses": float(s.closing_doses.median()),
            }
        )
    handles = [
        plt.Line2D([], [], color=BLUE, linewidth=1.5, label="Closing stock"),
        plt.Line2D([], [], color=INK_2, linestyle=(0, (3, 2)), label=f"Minimum ({min_weeks:g} weeks of use)"),
        plt.Rectangle((0, 0), 1, 1, color=DISRUPTION_FILL, label="Supply disruption"),
        plt.Rectangle((0, 0), 1, 1, color=STOCKOUT_FILL, label="Stock-out week"),
    ]
    fig.legend(handles=handles, loc="upper left", ncols=4, bbox_to_anchor=(0.02, 1.04), fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "F-D5_stock_vs_minimum.png")
    plt.close(fig)
    return "F-D5_stock_vs_minimum.png", pd.DataFrame(rows)


def fig_registry(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    children = d.csv("app/children.csv")
    facilities = d.csv("app/facilities.csv")
    counts = children.groupby("registration_facility_code").size().rename("registered_children")
    table = facilities[["facility_code", "name", "keph_level"]].merge(
        counts, left_on="facility_code", right_index=True
    )
    table = table.sort_values(["keph_level", "registered_children"], ascending=[True, False])
    colors = {"dispensary": BLUE, "health_centre": ORANGE, "sub_county_hospital": AQUA}
    hatches = {"dispensary": None, "health_centre": "////", "sub_county_hospital": "...."}
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 3.6))
    y = np.arange(len(table))[::-1]
    for level, label in LEVELS.items():
        mask = (table.keph_level == level).to_numpy()
        bars = ax.barh(
            y[mask],
            table.registered_children[mask],
            color=colors[level],
            hatch=hatches[level],
            edgecolor="white",
            height=0.7,
            label=label,
        )
        ax.bar_label(bars, fmt="{:,.0f}", fontsize=7.5, color=INK_2, padding=2)
    ax.set_yticks(y, table.facility_code)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Registered children")
    ax.legend(loc="lower left", ncols=3, bbox_to_anchor=(0, 1.0))
    fig.savefig(out / "F-D6_registry_by_facility.png")
    plt.close(fig)
    table = table.assign(keph_level=table.keph_level.map(LEVELS))
    return "F-D6_registry_by_facility.png", table


def fig_import_defects(d: RunData, out: Path) -> tuple[str, pd.DataFrame]:
    truth = d.csv("imports/import_dirty_truth.csv")
    totals = {
        "immunizations": len(d.csv("imports/import_immunizations_dirty.csv")),
        "stock": len(d.csv("imports/import_stock_dirty.csv")),
    }
    table = truth.groupby(["file", "defect"]).size().rename("rows").reset_index()
    table = table.sort_values(["file", "rows"], ascending=[True, False])
    fig, axes = plt.subplots(
        1, 2, figsize=(WIDTH_IN, 2.8), gridspec_kw={"width_ratios": [7, 4]}, sharex=False
    )
    for ax, (file, grp) in zip(axes, table.groupby("file", sort=True), strict=True):
        y = np.arange(len(grp))[::-1]
        bars = ax.barh(y, grp.rows, color=BLUE, height=0.7)
        ax.bar_label(bars, fontsize=7.5, color=INK_2, padding=2)
        ax.set_yticks(y, [s.replace("_", " ").lower() for s in grp.defect])
        ax.grid(axis="y", visible=False)
        ax.set_title(f"{file} ({totals[file]:,} rows)", fontsize=9, loc="left", color=INK)
        ax.set_xlabel("Defective rows")
    fig.tight_layout()
    fig.savefig(out / "F-D7_import_defects.png")
    plt.close(fig)
    table["share_of_file_pct"] = [
        round(100 * r / totals[f], 1) for f, r in zip(table.file, table.rows, strict=True)
    ]
    return "F-D7_import_defects.png", table


DATASET_ROLES = {
    "app": "Loaded by the application",
    "truth": "Evaluation only, never loaded",
    "imports": "Import-cleaning test only",
}
FILE_PURPOSE = {
    "facilities": "Fictional facilities and their KEPH level",
    "antigens": "Vaccines, vial size, open-vial policy",
    "schedule": "KEPI dose rules: recommended, minimum and maximum age, minimum interval",
    "sessions": "Fixed and outreach immunization sessions",
    "children": "Registered children (synthetic names, no phone numbers)",
    "immunization_events": "Doses given: child, dose, date, facility, session, lot",
    "stock_transactions": "Stock ledger: opening balances, receipts, issues, wastage, losses",
    "vaccine_lots": "Vaccine lots and first receipt date",
    "children_truth": "Every child born (including never-registered zero-dose children), background, dropout",
    "weekly_stock": "Facility x antigen x week: true demand, administered, unmet, wastage, stock-out flag",
    "stockout_turned_away": "Every dose refused because of a stock-out",
    "import_immunizations_dirty": "Immunization import sample with planted defects",
    "import_stock_dirty": "Stock import sample with planted defects",
    "import_dirty_truth": "Answer key: row and defect type for every planted defect",
}


def dataset_table(d: RunData) -> pd.DataFrame:
    rows = []
    for rel, meta in d.manifest["files"].items():
        folder, _, name = rel.partition("/")
        if folder not in DATASET_ROLES:
            continue
        stem = name.removesuffix(".csv")
        columns = list(pd.read_csv(d.run_dir / rel, nrows=0).columns)
        rows.append(
            {
                "folder": folder,
                "file": name,
                "rows": f"{meta['rows']:,}",
                "columns": len(columns),
                "column_names": ", ".join(columns),
                "content": FILE_PURPOSE.get(stem, "VERIFY"),
                "use": DATASET_ROLES[folder],
            }
        )
    return pd.DataFrame(rows)


FIGURES = [
    fig_calibration,
    fig_dropout,
    fig_timeliness,
    fig_weekly_demand,
    fig_stock_levels,
    fig_registry,
    fig_import_defects,
    fig_subgroups,
]


def run_eda(run_dir: Path, out: Path) -> Path:
    _style()
    out.mkdir(parents=True, exist_ok=True)
    d = RunData(run_dir)
    m = d.manifest
    lines = [
        f"# EDA evidence: {run_dir.name}",
        "",
        f"Generated {dt.date.today().isoformat()} by `immdss eda`. Run seed {m.get('seed')}, "
        f"config hash `{m.get('config_sha256', '')[:8]}`, git commit `{m.get('git_commit', 'n/a')}`. "
        "Validation: PASS. Each figure is followed by its data table (table alternative and evidence).",
        "",
        "## T-5.1 Dataset description",
        "",
        _md_table(dataset_table(d)),
    ]
    for fig in FIGURES:
        name, table = fig(d, out)
        lines += ["", f"## {name.split('_')[0]}", "", f"![{name}]({name})", "", _md_table(table)]
    report = out / f"EDA_{run_dir.name}.md"
    report.write_text("\n".join(lines) + "\n")
    return report
