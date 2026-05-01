"""Build country exposure output from ETF country percentage data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .file_helpers import ensure_folder_exists


ETF_COUNTRY_ID_COLUMNS = ["ETF Name", "Stock Code"]
COUNTRY_EXPOSURE_BASE_COLUMNS = ["stock_name", "stock_code", "currency"]
REQUIRED_POSITION_COLUMNS = COUNTRY_EXPOSURE_BASE_COLUMNS + ["market_value"]
COUNTRY_TOTAL_COLUMNS = ["currency", "country", "investment_value"]


def load_etf_country_matrix(matrix_path: Path) -> pd.DataFrame:
    """Load the ETF country matrix, returning an empty schema if it is absent."""
    if not matrix_path.exists():
        return pd.DataFrame(columns=ETF_COUNTRY_ID_COLUMNS)

    matrix = pd.read_csv(matrix_path)
    missing_columns = [
        column for column in ETF_COUNTRY_ID_COLUMNS if column not in matrix.columns
    ]
    if missing_columns:
        raise ValueError(
            "ETF country matrix is missing required column(s): "
            + ", ".join(missing_columns)
        )

    matrix = matrix.copy()
    matrix["Stock Code"] = normalize_stock_code(matrix["Stock Code"])
    country_columns = get_country_columns(matrix)
    matrix[country_columns] = (
        matrix[country_columns].apply(pd.to_numeric, errors="coerce").fillna(0)
    )
    return matrix.drop_duplicates("Stock Code")


def build_country_exposure_dataframe(
    positions_df: pd.DataFrame, etf_country_matrix: pd.DataFrame
) -> pd.DataFrame:
    """Multiply ETF country percentages by position market value."""
    validate_positions_columns(positions_df)

    country_columns = get_country_columns(etf_country_matrix)
    exposure = positions_df[REQUIRED_POSITION_COLUMNS].copy()
    exposure["stock_code"] = normalize_stock_code(exposure["stock_code"])
    exposure["market_value"] = pd.to_numeric(
        exposure["market_value"], errors="coerce"
    ).fillna(0)

    matrix = etf_country_matrix.copy()
    if "Stock Code" not in matrix.columns:
        matrix["Stock Code"] = pd.Series(dtype=object)
    matrix["Stock Code"] = normalize_stock_code(matrix["Stock Code"])

    joined = exposure.merge(
        matrix[["Stock Code", *country_columns]],
        how="left",
        left_on="stock_code",
        right_on="Stock Code",
    )
    if country_columns:
        joined[country_columns] = joined[country_columns].fillna(0)
        joined[country_columns] = joined[country_columns].multiply(
            joined["market_value"], axis=0
        ) / 100

    return joined[COUNTRY_EXPOSURE_BASE_COLUMNS + country_columns]


def build_country_exposure_totals_dataframe(
    country_exposure_df: pd.DataFrame,
) -> pd.DataFrame:
    """Pivot wide country exposure rows into currency/country investment totals."""
    if country_exposure_df.empty:
        return pd.DataFrame(columns=COUNTRY_TOTAL_COLUMNS)
    if "currency" not in country_exposure_df.columns:
        raise ValueError("country exposure dataframe is missing required column: currency")

    country_columns = [
        column
        for column in country_exposure_df.columns
        if column not in COUNTRY_EXPOSURE_BASE_COLUMNS
    ]
    if not country_columns:
        return pd.DataFrame(columns=COUNTRY_TOTAL_COLUMNS)

    exposure = country_exposure_df[["currency", *country_columns]].copy()
    exposure[country_columns] = exposure[country_columns].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0)
    totals = exposure.melt(
        id_vars=["currency"],
        value_vars=country_columns,
        var_name="country",
        value_name="investment_value",
    )
    totals = (
        totals.groupby(["currency", "country"], as_index=False)["investment_value"]
        .sum()
        .sort_values(["currency", "investment_value"], ascending=[True, False])
    )
    totals = totals[totals["investment_value"] > 0].reset_index(drop=True)
    return totals[COUNTRY_TOTAL_COLUMNS]


def save_country_exposure_pie_charts(
    country_totals_df: pd.DataFrame,
    output_path: Path,
    max_slices: int = 5,
) -> None:
    """Save one country exposure pie chart per currency."""
    if country_totals_df.empty:
        print("No country exposure totals found. Skipping country exposure pie charts.")
        return

    from .chart_helpers import set_matplotlib_cache_dir

    set_matplotlib_cache_dir()
    import matplotlib.pyplot as plt
    import seaborn as sns

    ensure_folder_exists(output_path)
    sns.set_theme(
        style="white",
        context="notebook",
        rc={
            "font.family": "sans-serif",
            "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans", "sans-serif"],
        },
    )

    chart_totals = country_totals_df.copy()
    chart_totals["investment_value"] = pd.to_numeric(
        chart_totals["investment_value"], errors="coerce"
    )
    chart_totals = chart_totals.dropna(subset=["investment_value"])

    for currency in chart_totals["currency"].dropna().unique():
        currency_totals = chart_totals[chart_totals["currency"] == currency]
        currency_totals = aggregate_country_totals_for_pie(
            currency_totals,
            max_slices=max_slices,
        )
        if currency_totals.empty:
            continue

        chart_file = (
            output_path
            / f"country_exposure_pie_{currency}_{pd.Timestamp.today().date().isoformat()}.png"
        )
        action = "Overwriting existing" if chart_file.exists() else "Creating new"

        colors = sns.color_palette("Set2", n_colors=len(currency_totals))
        fig, axis = plt.subplots(figsize=(9.5, 7.2))
        axis.pie(
            currency_totals["investment_value"],
            labels=currency_totals["country"],
            autopct="%1.1f%%",
            pctdistance=0.78,
            labeldistance=1.08,
            startangle=90,
            colors=colors,
            textprops={"fontsize": 10},
        )
        axis.set_title(
            f"Country Exposure - {currency}",
            fontsize=16,
            weight="semibold",
            pad=18,
        )
        axis.set_aspect("equal")
        plt.tight_layout()
        plt.savefig(chart_file, dpi=150)
        plt.close(fig)

        print(f"{action} country exposure pie chart: {chart_file}")


def aggregate_country_totals_for_pie(
    country_totals_df: pd.DataFrame,
    max_slices: int = 5,
) -> pd.DataFrame:
    """Keep top country slices and aggregate the rest into Others."""
    if country_totals_df.empty:
        return country_totals_df.copy()
    if max_slices < 2:
        raise ValueError("max_slices must be at least 2")

    sorted_totals = country_totals_df.sort_values(
        "investment_value", ascending=False
    ).reset_index(drop=True)
    if len(sorted_totals) <= max_slices:
        return sorted_totals

    visible_count = max_slices - 1
    visible_totals = sorted_totals.head(visible_count).copy()
    others_total = sorted_totals.iloc[visible_count:]["investment_value"].sum()
    if others_total <= 0:
        return visible_totals

    others_row = {
        "currency": sorted_totals.loc[0, "currency"],
        "country": "Others",
        "investment_value": others_total,
    }
    return pd.concat(
        [visible_totals, pd.DataFrame([others_row])],
        ignore_index=True,
    )


def fill_missing_stock_codes_from_mapping(
    positions_df: pd.DataFrame, stock_code_mapping: pd.DataFrame
) -> pd.DataFrame:
    """Fill blank position stock codes from current and historical stock names."""
    if positions_df.empty or stock_code_mapping.empty:
        return positions_df.copy()
    if "stock_name" not in positions_df.columns or "stock_code" not in positions_df.columns:
        return positions_df.copy()

    stock_code_by_name = build_stock_code_lookup(stock_code_mapping)
    if not stock_code_by_name:
        return positions_df.copy()

    positions = positions_df.copy()
    missing_code = (
        positions["stock_code"].isna()
        | (positions["stock_code"].astype(str).str.strip() == "")
    )
    mapped_codes = (
        positions.loc[missing_code, "stock_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .map(stock_code_by_name)
    )
    positions.loc[missing_code, "stock_code"] = positions.loc[
        missing_code, "stock_code"
    ].combine_first(mapped_codes)
    return positions


def build_stock_code_lookup(stock_code_mapping: pd.DataFrame) -> dict[str, str]:
    """Build a stock-name-to-code lookup from latest and old stock names."""
    stock_code_by_name: dict[str, str] = {}
    for _, row in stock_code_mapping.iterrows():
        stock_code = row.get("stock_code")
        if pd.isna(stock_code):
            continue

        code = str(stock_code).strip()
        if not code:
            continue

        add_stock_name_lookup(stock_code_by_name, row.get("stock_name"), code)
        old_stock_names = row.get("old_stock_names", pd.NA)
        if pd.isna(old_stock_names):
            continue
        for old_stock_name in str(old_stock_names).split("|"):
            add_stock_name_lookup(stock_code_by_name, old_stock_name, code)

    return stock_code_by_name


def add_stock_name_lookup(
    stock_code_by_name: dict[str, str], stock_name: object, stock_code: str
) -> None:
    """Add a normalized stock name lookup when the name is present."""
    if pd.isna(stock_name):
        return

    normalized_name = str(stock_name).strip().upper()
    if normalized_name:
        stock_code_by_name.setdefault(normalized_name, stock_code)


def validate_positions_columns(positions_df: pd.DataFrame) -> None:
    """Raise a helpful error when positions are missing required fields."""
    missing_columns = [
        column for column in REQUIRED_POSITION_COLUMNS if column not in positions_df.columns
    ]
    if missing_columns:
        raise ValueError(
            "positions dataframe is missing required column(s): "
            + ", ".join(missing_columns)
        )


def get_country_columns(etf_country_matrix: pd.DataFrame) -> list[str]:
    """Return matrix country columns in source order."""
    return [
        column
        for column in etf_country_matrix.columns
        if column not in ETF_COUNTRY_ID_COLUMNS
    ]


def normalize_stock_code(stock_codes: pd.Series) -> pd.Series:
    """Normalize stock codes for matching broker positions to ETF rows."""
    return stock_codes.fillna("").astype(str).str.strip().str.upper()
