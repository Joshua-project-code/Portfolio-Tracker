# This module builds chart-ready summaries and saves Seaborn and Plotly charts
# for broker positions and transactions. It contains helpers for the Matplotlib
# cache directory used by Seaborn, monthly position and transaction totals,
# monthly line charts, currency-separated position distribution pie charts, and
# aggregation of pie slices into an Others category.

from __future__ import annotations

import os
from datetime import date
from datetime import datetime
from pathlib import Path

import pandas as pd

from .file_helpers import ensure_folder_exists

CHART_FONTS = {
    "title": 20,
    "subtitle": 17,
    "axis_label": 14,
    "tick": 11,
    "legend_title": 13,
    "legend": 11,
    "pie_percent": 11,
}
PLOTLY_FONT_FAMILY = "Inter, Segoe UI, Roboto, Arial, sans-serif"
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
    workbooks: list[Path], csv_files: list[Path], fill_missing_months: bool = False
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
    grouped = (
        monthly_totals.groupby(["month", "series"], as_index=False)["market_value"]
        .sum()
        .sort_values(["month", "series"], ignore_index=True)
    )
    if not fill_missing_months:
        return grouped
    return complete_monthly_series(grouped, "market_value")


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

    grouped = (
        monthly_transactions.groupby(["month", "series"], as_index=False)[
            "transaction_amount"
        ]
        .sum()
        .sort_values(["month", "series"], ignore_index=True)
    )
    return complete_monthly_series(grouped, "transaction_amount")


def complete_monthly_series(
    grouped: pd.DataFrame,
    value_column: str,
) -> pd.DataFrame:
    """Fill missing month/series combinations with zero for chart continuity."""
    if grouped.empty:
        return grouped

    month_range = pd.date_range(
        grouped["month"].min(),
        grouped["month"].max(),
        freq="MS",
    )
    series_values = sorted(grouped["series"].dropna().unique().tolist())
    full_index = pd.MultiIndex.from_product(
        [month_range, series_values], names=["month", "series"]
    )

    completed = (
        grouped.set_index(["month", "series"])
        .reindex(full_index, fill_value=0)
        .reset_index()
    )
    completed[value_column] = pd.to_numeric(
        completed[value_column], errors="coerce"
    ).fillna(0)

    return completed.sort_values(["month", "series"], ignore_index=True)


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
    import matplotlib.dates as mdates
    import seaborn as sns

    ensure_folder_exists(output_path)
    chart_file = output_path / f"{filename_prefix}_{date.today().isoformat()}.png"
    action = "Overwriting existing" if chart_file.exists() else "Creating new"

    chart_data = monthly_totals.copy()
    chart_data["month"] = pd.to_datetime(chart_data["month"])
    sns.set_theme(
        style="whitegrid",
        context="notebook",
        rc={
            "font.family": "sans-serif",
            "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans", "sans-serif"],
        },
    )
    series_count = max(chart_data["series"].nunique(), 1)
    month_count = max(chart_data["month"].nunique(), 1)
    fig_height = max(7.2, 5.8 + series_count * 0.22)
    fig_width = max(14.0, 8.0 + month_count * 0.45)
    fig, axis = plt.subplots(figsize=(fig_width, fig_height))
    sns.lineplot(
        data=chart_data,
        x="month",
        y=value_column,
        hue="series",
        marker="o",
        markersize=7,
        linewidth=2.2,
        ax=axis,
    )
    axis.set_title(chart_title, fontsize=CHART_FONTS["title"], pad=16, weight="semibold")
    axis.set_xlabel("Month", fontsize=CHART_FONTS["axis_label"], labelpad=10)
    axis.set_ylabel(y_label, fontsize=CHART_FONTS["axis_label"], labelpad=10)
    axis.tick_params(axis="both", labelsize=CHART_FONTS["tick"])
    axis.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axis.margins(x=0.04)
    handles, labels = axis.get_legend_handles_labels()
    if axis.get_legend() is not None:
        axis.get_legend().remove()
    fig.legend(
        handles,
        labels,
        title="Broker - Currency",
        loc="center left",
        bbox_to_anchor=(0.75, 0.5),
        ncol=1,
        fontsize=CHART_FONTS["legend"],
        title_fontsize=CHART_FONTS["legend_title"],
        frameon=True,
        borderpad=0.8,
        labelspacing=0.6,
        columnspacing=1.4,
    )
    fig.autofmt_xdate(rotation=30, ha="right")
    fig.subplots_adjust(left=0.09, right=0.72, top=0.88, bottom=0.20)
    try:
        plt.savefig(chart_file, dpi=150)
    except PermissionError:
        fallback_file = chart_file.with_name(
            f"{chart_file.stem}_{datetime.now().strftime('%H%M%S')}{chart_file.suffix}"
        )
        chart_file = fallback_file
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
    chart_data["month_label"] = chart_data["month"].dt.strftime("%Y-%m")
    figure = px.line(
        chart_data,
        x="month_label",
        y=value_column,
        color="series",
        markers=True,
        title=chart_title,
        labels={
            "month_label": "Month",
            value_column: y_label,
            "series": "Broker - Currency",
        },
    )
    figure.update_layout(
        template="plotly_white",
        height=620,
        font={"family": PLOTLY_FONT_FAMILY, "size": 13, "color": "#1f2933"},
        title={"font": {"size": 22}, "x": 0.02, "xanchor": "left"},
        xaxis={
            "title_font": {"size": 15},
            "tickfont": {"size": 12},
            "automargin": True,
            "type": "category",
            "categoryorder": "array",
            "categoryarray": chart_data["month_label"].drop_duplicates().tolist(),
        },
        yaxis={"title_font": {"size": 15}, "tickfont": {"size": 12}, "automargin": True},
        legend_title_text="Broker - Currency",
        legend={
            "orientation": "v",
            "x": 1.02,
            "y": 1,
            "xanchor": "left",
            "yanchor": "top",
            "font": {"size": 12},
            "title": {"font": {"size": 13}},
        },
        margin={"t": 80, "b": 90, "l": 90, "r": 260},
    )
    figure.update_traces(
        mode="lines+markers",
        marker={"size": 8},
        connectgaps=False,
    )
    try:
        figure.write_html(chart_file, include_plotlyjs=True, full_html=True)
    except PermissionError:
        fallback_file = chart_file.with_name(
            f"{chart_file.stem}_{datetime.now().strftime('%H%M%S')}{chart_file.suffix}"
        )
        chart_file = fallback_file
        figure.write_html(chart_file, include_plotlyjs=True, full_html=True)

    print(f"{action} {action_label}: {chart_file}")


def save_seaborn_position_distribution_pie_chart(
    positions_df: pd.DataFrame,
    category_column: str,
    chart_title: str,
    filename_prefix: str,
    output_path: Path,
) -> None:
    """Save one Seaborn pie chart file per currency."""
    if positions_df.empty:
        print(f"No investment position data found. Skipping Seaborn {chart_title.lower()} chart.")
        return

    set_matplotlib_cache_dir()
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import seaborn as sns

    ensure_folder_exists(output_path)
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

    sns.set_theme(
        style="white",
        context="notebook",
        rc={
            "font.family": "sans-serif",
            "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans", "sans-serif"],
        },
    )
    currencies = totals["currency"].dropna().unique()
    for currency in currencies:
        currency_totals = totals[totals["currency"] == currency]
        currency_totals = aggregate_small_pie_slices(
            currency_totals, category_column, "market_value", max_slices=6
        )
        if currency_totals.empty:
            continue

        chart_file = output_path / (
            f"seaborn_{filename_prefix}_{currency}_{date.today().isoformat()}.png"
        )
        action = "Overwriting existing" if chart_file.exists() else "Creating new"
        legend_labels = currency_totals[category_column].astype(str).tolist()
        palette = sns.color_palette("Set2", n_colors=max(len(legend_labels), 1))
        color_by_label = dict(zip(legend_labels, palette))
        fig_height = max(8.0, 6.6 + len(legend_labels) * 0.24)
        fig, axis = plt.subplots(figsize=(10.5, fig_height))
        colors = [
            color_by_label[str(label)]
            for label in currency_totals[category_column].astype(str)
        ]
        axis.pie(
            currency_totals["market_value"],
            autopct="%1.1f%%",
            pctdistance=0.72,
            startangle=90,
            radius=1.0,
            colors=colors,
            textprops={"fontsize": CHART_FONTS["pie_percent"]},
        )
        axis.set_title(f"{chart_title} - {currency}", fontsize=CHART_FONTS["title"], pad=14, weight="semibold")
        axis.set_aspect("equal")
        legend_handles = [
            Patch(facecolor=color_by_label[label], label=label)
            for label in legend_labels
        ]
        fig.legend(
            handles=legend_handles,
            title=category_column.replace("_", " ").title(),
            loc="center left",
            bbox_to_anchor=(0.78, 0.5),
            fontsize=CHART_FONTS["legend"],
            title_fontsize=CHART_FONTS["legend_title"],
            ncol=1,
            frameon=True,
            borderpad=0.8,
            labelspacing=0.6,
            columnspacing=1.4,
        )
        fig.subplots_adjust(left=0.05, right=0.74, top=0.86, bottom=0.08)
        try:
            plt.savefig(chart_file, dpi=150)
        except PermissionError:
            fallback_file = chart_file.with_name(
                f"{chart_file.stem}_{datetime.now().strftime('%H%M%S')}{chart_file.suffix}"
            )
            chart_file = fallback_file
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
    """Save one Plotly pie chart HTML file per currency."""
    if positions_df.empty:
        print(f"No investment position data found. Skipping Plotly {chart_title.lower()} chart.")
        return

    import plotly.graph_objects as go

    ensure_folder_exists(output_path)

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
    for currency in currencies:
        currency_totals = totals[totals["currency"] == currency]
        currency_totals = aggregate_small_pie_slices(
            currency_totals, category_column, "market_value", max_slices=6
        )
        if currency_totals.empty:
            continue
        chart_file = output_path / (
            f"plotly_{filename_prefix}_{currency}_{date.today().isoformat()}.html"
        )
        action = "Overwriting existing" if chart_file.exists() else "Creating new"
        figure = go.Figure(
            go.Pie(
                labels=currency_totals[category_column],
                values=currency_totals["market_value"],
                name=str(currency),
                textinfo="label+percent",
                hovertemplate="%{label}<br>%{value:,.2f}<br>%{percent}<extra></extra>",
            )
        )
        figure.update_layout(
            title_text=f"{chart_title} - {currency}",
            template="plotly_white",
            height=700,
            font={"family": PLOTLY_FONT_FAMILY, "size": 13, "color": "#1f2933"},
            title={"font": {"size": 22}, "x": 0.02, "xanchor": "left"},
            showlegend=True,
            legend={
                "orientation": "v",
                "x": 1.02,
                "y": 1,
                "xanchor": "left",
                "yanchor": "top",
                "font": {"size": 12},
                "title": {"font": {"size": 13}},
            },
            margin={"t": 80, "b": 90, "l": 60, "r": 260},
        )
        try:
            figure.write_html(chart_file, include_plotlyjs=True, full_html=True)
        except PermissionError:
            fallback_file = chart_file.with_name(
                f"{chart_file.stem}_{datetime.now().strftime('%H%M%S')}{chart_file.suffix}"
            )
            chart_file = fallback_file
            figure.write_html(chart_file, include_plotlyjs=True, full_html=True)
        print(f"{action} plotly {chart_title.lower()} chart: {chart_file}")


def aggregate_small_pie_slices(
    totals: pd.DataFrame,
    category_column: str,
    value_column: str,
    max_slices: int,
) -> pd.DataFrame:
    """Keep top slices and aggregate the rest into Others."""
    if max_slices < 2:
        raise ValueError("max_slices must be at least 2")

    total_value = totals[value_column].sum()
    if total_value <= 0:
        return totals

    totals = totals.copy()
    totals = totals.sort_values(value_column, ascending=False).reset_index(drop=True)
    if len(totals) <= max_slices:
        return totals

    visible_count = max_slices - 1
    large_totals = totals.head(visible_count).copy()
    others_total = totals.iloc[visible_count:][value_column].sum()
    if others_total <= 0:
        return large_totals

    others_row = {column: pd.NA for column in large_totals.columns}
    others_row[category_column] = "Others"
    others_row[value_column] = others_total
    if "currency" in large_totals.columns and not totals["currency"].empty:
        others_row["currency"] = totals["currency"].iloc[0]

    return pd.concat([large_totals, pd.DataFrame([others_row])], ignore_index=True)
