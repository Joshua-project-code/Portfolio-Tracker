# This module builds chart-ready summaries and saves Seaborn and Plotly charts
# for broker positions and transactions. It contains helpers for the Matplotlib
# cache directory used by Seaborn, monthly position and transaction totals,
# monthly line charts, currency-separated position distribution pie charts, and
# aggregation of small pie slices into an Others category.

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd

from .file_helpers import ensure_folder_exists

SEABORN_FONT_SIZE = 28
from .interactive_brokers_parser import (
    parse_interactive_brokers_positions,
    parse_interactive_brokers_transactions,
)
from .poems_parser import (
    add_stock_codes_to_positions,
    parse_poems_positions,
    parse_poems_transactions,
)


def set_matplotlib_cache_dir() -> None:
    """Keep Matplotlib cache files inside the workspace and use a non-GUI backend."""
    os.environ.setdefault(
        "MPLCONFIGDIR", str(Path(__file__).resolve().parent.parent / ".matplotlib-cache")
    )
    os.environ.setdefault("MPLBACKEND", "Agg")

    import matplotlib

    matplotlib.use("Agg", force=True)


def build_monthly_position_totals(
    workbooks: list[Path], csv_files: list[Path]
) -> pd.DataFrame:
    """Build monthly total market value by broker and currency from each snapshot."""
    records: list[dict[str, object]] = []

    for workbook_path in workbooks:
        transactions = parse_poems_transactions(workbook_path)
        if transactions.empty:
            continue

        positions = parse_poems_positions(workbook_path)
        positions = add_stock_codes_to_positions(positions, transactions)
        month = transactions["transaction_date"].max().to_period("M").to_timestamp()
        position_totals = positions.groupby("currency", dropna=False)["market_value"].sum()
        for currency, market_value in position_totals.items():
            records.append(
                {
                    "month": month,
                    "series": f"poems - {currency}",
                    "market_value": market_value,
                }
            )

    for csv_path in csv_files:
        transactions = parse_interactive_brokers_transactions(csv_path)
        if transactions.empty:
            continue

        positions = parse_interactive_brokers_positions(csv_path)
        month = transactions["transaction_date"].max().to_period("M").to_timestamp()
        position_totals = positions.groupby("currency", dropna=False)["market_value"].sum()
        for currency, market_value in position_totals.items():
            records.append(
                {
                    "month": month,
                    "series": f"interactive brokers - {currency}",
                    "market_value": market_value,
                }
            )

    if not records:
        return pd.DataFrame(columns=["month", "series", "market_value"])

    monthly_totals = pd.DataFrame(records)
    return (
        monthly_totals.groupby(["month", "series"], as_index=False)["market_value"]
        .sum()
        .sort_values(["month", "series"], ignore_index=True)
    )


def save_seaborn_monthly_position_chart(
    monthly_totals: pd.DataFrame, output_path: Path
) -> None:
    """Save a Seaborn line chart of monthly total market value."""
    save_seaborn_monthly_line_chart(
        monthly_totals,
        output_path,
        value_column="market_value",
        filename_prefix="seaborn_investment_positions_by_month",
        chart_title="Monthly Investment Position by Broker and Currency",
        y_label="Total market value",
        empty_message="No monthly investment position data found. Skipping Seaborn line chart.",
        action_label="seaborn monthly investment position chart",
    )


def save_plotly_monthly_position_chart(
    monthly_totals: pd.DataFrame, output_path: Path
) -> None:
    """Save a Plotly line chart of monthly total market value."""
    save_plotly_monthly_line_chart(
        monthly_totals,
        output_path,
        value_column="market_value",
        filename_prefix="plotly_investment_positions_by_month",
        chart_title="Monthly Investment Position by Broker and Currency",
        y_label="Total market value",
        empty_message="No monthly investment position data found. Skipping Plotly line chart.",
        action_label="plotly monthly investment position chart",
    )


def build_monthly_transaction_totals(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Build monthly total transaction amount by broker and currency."""
    if transactions_df.empty:
        return pd.DataFrame(columns=["month", "series", "transaction_amount"])

    monthly_transactions = transactions_df.copy()
    monthly_transactions["month"] = (
        pd.to_datetime(monthly_transactions["transaction_date"])
        .dt.to_period("M")
        .dt.to_timestamp()
    )
    monthly_transactions["transaction_amount"] = pd.to_numeric(
        monthly_transactions["transaction_amount"], errors="coerce"
    )
    monthly_transactions["series"] = (
        monthly_transactions["broker"].astype(str)
        + " - "
        + monthly_transactions["price_currency"].astype(str)
    )

    return (
        monthly_transactions.groupby(["month", "series"], as_index=False)[
            "transaction_amount"
        ]
        .sum()
        .sort_values(["month", "series"], ignore_index=True)
    )


def save_seaborn_monthly_transaction_chart(
    monthly_totals: pd.DataFrame, output_path: Path
) -> None:
    """Save a Seaborn line chart of monthly total transaction amount."""
    save_seaborn_monthly_line_chart(
        monthly_totals,
        output_path,
        value_column="transaction_amount",
        filename_prefix="seaborn_transactions_by_month",
        chart_title="Monthly Transaction Amount by Broker and Currency",
        y_label="Total transaction amount",
        empty_message="No monthly transaction data found. Skipping Seaborn line chart.",
        action_label="seaborn monthly transaction chart",
    )


def save_plotly_monthly_transaction_chart(
    monthly_totals: pd.DataFrame, output_path: Path
) -> None:
    """Save a Plotly line chart of monthly total transaction amount."""
    save_plotly_monthly_line_chart(
        monthly_totals,
        output_path,
        value_column="transaction_amount",
        filename_prefix="plotly_transactions_by_month",
        chart_title="Monthly Transaction Amount by Broker and Currency",
        y_label="Total transaction amount",
        empty_message="No monthly transaction data found. Skipping Plotly line chart.",
        action_label="plotly monthly transaction chart",
    )


def save_seaborn_monthly_line_chart(
    monthly_totals: pd.DataFrame,
    output_path: Path,
    value_column: str,
    filename_prefix: str,
    chart_title: str,
    y_label: str,
    empty_message: str,
    action_label: str,
) -> None:
    """Save a Seaborn line chart from monthly totals."""
    if monthly_totals.empty:
        print(empty_message)
        return

    set_matplotlib_cache_dir()
    import matplotlib.pyplot as plt
    import seaborn as sns

    ensure_folder_exists(output_path)
    chart_file = output_path / f"{filename_prefix}_{date.today().isoformat()}.png"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_data = monthly_totals.copy()
    chart_data["month"] = pd.to_datetime(chart_data["month"])
    sns.set_theme(style="whitegrid", context="talk")
    fig, axis = plt.subplots(figsize=(12, 9.0))
    sns.lineplot(
        data=chart_data,
        x="month",
        y=value_column,
        hue="series",
        marker="o",
        linewidth=2.2,
        ax=axis,
    )
    axis.set_title(chart_title, fontsize=SEABORN_FONT_SIZE, pad=20)
    axis.set_xlabel("Month", fontsize=SEABORN_FONT_SIZE)
    axis.set_ylabel(y_label, fontsize=SEABORN_FONT_SIZE)
    axis.tick_params(axis="both", labelsize=SEABORN_FONT_SIZE)
    handles, labels = axis.get_legend_handles_labels()
    if axis.get_legend() is not None:
        axis.get_legend().remove()
    fig.legend(
        handles,
        labels,
        title="Broker - Currency",
        loc="center left",
        bbox_to_anchor=(0.72, 0.5),
        ncol=1,
        fontsize=SEABORN_FONT_SIZE,
        title_fontsize=SEABORN_FONT_SIZE,
        frameon=False,
    )
    fig.autofmt_xdate()
    fig.subplots_adjust(left=0.10, right=0.68, top=0.88, bottom=0.24)
    plt.savefig(chart_file, dpi=150)
    plt.close()

    print(f"{action} {action_label}: {chart_file}")


def save_plotly_monthly_line_chart(
    monthly_totals: pd.DataFrame,
    output_path: Path,
    value_column: str,
    filename_prefix: str,
    chart_title: str,
    y_label: str,
    empty_message: str,
    action_label: str,
) -> None:
    """Save a Plotly line chart from monthly totals as an HTML file."""
    if monthly_totals.empty:
        print(empty_message)
        return

    import plotly.express as px

    ensure_folder_exists(output_path)
    chart_file = output_path / f"{filename_prefix}_{date.today().isoformat()}.html"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_data = monthly_totals.copy()
    chart_data["month"] = pd.to_datetime(chart_data["month"])
    figure = px.line(
        chart_data,
        x="month",
        y=value_column,
        color="series",
        markers=True,
        title=chart_title,
        labels={
            "month": "Month",
            value_column: y_label,
            "series": "Broker - Currency",
        },
    )
    figure.update_layout(
        template="plotly_white",
        height=620,
        legend_title_text="Broker - Currency",
        legend={
            "orientation": "v",
            "x": 1.02,
            "y": 1,
            "xanchor": "left",
            "yanchor": "top",
        },
        margin={"b": 80, "r": 220},
    )
    figure.write_html(chart_file, include_plotlyjs=True, full_html=True)

    print(f"{action} {action_label}: {chart_file}")


def save_seaborn_position_distribution_pie_chart(
    positions_df: pd.DataFrame,
    category_column: str,
    chart_title: str,
    filename_prefix: str,
    output_path: Path,
) -> None:
    """Save currency-separated pie charts using Seaborn styling and palettes."""
    if positions_df.empty:
        print(f"No investment position data found. Skipping Seaborn {chart_title.lower()} chart.")
        return

    set_matplotlib_cache_dir()
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import seaborn as sns

    ensure_folder_exists(output_path)
    chart_file = output_path / f"seaborn_{filename_prefix}_{date.today().isoformat()}.png"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_positions = positions_df.copy()
    chart_positions["market_value"] = pd.to_numeric(
        chart_positions["market_value"], errors="coerce"
    )
    chart_positions = chart_positions.dropna(subset=["market_value"])
    totals = (
        chart_positions.groupby(["currency", category_column], as_index=False)[
            "market_value"
        ]
        .sum()
        .sort_values(["currency", "market_value"], ascending=[True, False])
    )
    if totals.empty:
        print(f"No chartable investment position data found. Skipping Seaborn {chart_title.lower()} chart.")
        return

    sns.set_theme(style="white", context="talk")
    currencies = totals["currency"].dropna().unique()
    fig, axes = plt.subplots(1, len(currencies), figsize=(12 * len(currencies), 17.25))
    if len(currencies) == 1:
        axes = [axes]
    fig.subplots_adjust(left=0.04, right=0.78, top=0.84, bottom=0.06, wspace=0.32)

    currency_chart_data = []
    legend_labels = []
    for currency in currencies:
        currency_totals = totals[totals["currency"] == currency]
        currency_totals = aggregate_small_pie_slices(
            currency_totals, category_column, "market_value", threshold=0.10
        )
        currency_chart_data.append((currency, currency_totals))
        for label in currency_totals[category_column].astype(str):
            if label not in legend_labels:
                legend_labels.append(label)

    palette = sns.color_palette("Set2", n_colors=max(len(legend_labels), 1))
    color_by_label = dict(zip(legend_labels, palette))

    for axis, (currency, currency_totals) in zip(axes, currency_chart_data):
        colors = [
            color_by_label[str(label)]
            for label in currency_totals[category_column].astype(str)
        ]
        axis.pie(
            currency_totals["market_value"],
            autopct="%1.1f%%",
            pctdistance=0.72,
            startangle=90,
            radius=1.28,
            colors=colors,
            textprops={"fontsize": SEABORN_FONT_SIZE},
        )
        axis.set_title(f"{currency}", fontsize=SEABORN_FONT_SIZE, pad=22)
        axis.set_aspect("equal")

    fig.suptitle(chart_title, fontsize=SEABORN_FONT_SIZE)
    legend_handles = [
        Patch(facecolor=color_by_label[label], label=label)
        for label in legend_labels
    ]
    fig.legend(
        handles=legend_handles,
        title=category_column.replace("_", " ").title(),
        loc="center left",
        bbox_to_anchor=(0.80, 0.5),
        fontsize=SEABORN_FONT_SIZE,
        title_fontsize=SEABORN_FONT_SIZE,
        ncol=1,
        frameon=False,
    )
    plt.savefig(chart_file, dpi=150)
    plt.close()

    print(f"{action} seaborn {chart_title.lower()} chart: {chart_file}")


def save_plotly_position_distribution_pie_chart(
    positions_df: pd.DataFrame,
    category_column: str,
    chart_title: str,
    filename_prefix: str,
    output_path: Path,
) -> None:
    """Save currency-separated Plotly pie charts as an HTML file."""
    if positions_df.empty:
        print(f"No investment position data found. Skipping Plotly {chart_title.lower()} chart.")
        return

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    ensure_folder_exists(output_path)
    chart_file = output_path / f"plotly_{filename_prefix}_{date.today().isoformat()}.html"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_positions = positions_df.copy()
    chart_positions["market_value"] = pd.to_numeric(
        chart_positions["market_value"], errors="coerce"
    )
    chart_positions = chart_positions.dropna(subset=["market_value"])
    totals = (
        chart_positions.groupby(["currency", category_column], as_index=False)[
            "market_value"
        ]
        .sum()
        .sort_values(["currency", "market_value"], ascending=[True, False])
    )
    if totals.empty:
        print(f"No chartable investment position data found. Skipping Plotly {chart_title.lower()} chart.")
        return

    currencies = totals["currency"].dropna().unique()
    figure = make_subplots(
        rows=1,
        cols=len(currencies),
        specs=[[{"type": "domain"} for _ in currencies]],
        subplot_titles=[str(currency) for currency in currencies],
    )
    for index, currency in enumerate(currencies, start=1):
        currency_totals = totals[totals["currency"] == currency]
        currency_totals = aggregate_small_pie_slices(
            currency_totals, category_column, "market_value", threshold=0.10
        )
        figure.add_trace(
            go.Pie(
                labels=currency_totals[category_column],
                values=currency_totals["market_value"],
                name=str(currency),
                textinfo="label+percent",
                hovertemplate="%{label}<br>%{value:,.2f}<br>%{percent}<extra></extra>",
            ),
            row=1,
            col=index,
        )

    figure.update_layout(
        title_text=chart_title,
        template="plotly_white",
        height=720,
        showlegend=True,
        legend={
            "orientation": "v",
            "x": 1.02,
            "y": 1,
            "xanchor": "left",
            "yanchor": "top",
        },
        margin={"b": 80, "r": 220},
    )
    figure.write_html(chart_file, include_plotlyjs=True, full_html=True)

    print(f"{action} plotly {chart_title.lower()} chart: {chart_file}")


def aggregate_small_pie_slices(
    totals: pd.DataFrame,
    category_column: str,
    value_column: str,
    threshold: float,
) -> pd.DataFrame:
    """Aggregate pie slices below the percentage threshold into Others."""
    total_value = totals[value_column].sum()
    if total_value <= 0:
        return totals

    totals = totals.copy()
    totals["percentage"] = totals[value_column] / total_value
    small_slices = totals["percentage"] < threshold
    if not small_slices.any():
        return totals.drop(columns=["percentage"])

    large_totals = totals.loc[~small_slices].drop(columns=["percentage"])
    others_total = totals.loc[small_slices, value_column].sum()
    if others_total <= 0:
        return large_totals

    others_row = {column: pd.NA for column in large_totals.columns}
    others_row[category_column] = "Others"
    others_row[value_column] = others_total
    if "currency" in large_totals.columns and not totals["currency"].empty:
        others_row["currency"] = totals["currency"].iloc[0]

    return pd.concat([large_totals, pd.DataFrame([others_row])], ignore_index=True)
