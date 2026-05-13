# This module calculates Portfolio Tracker performance metrics from runtime
# DataFrames. It normalizes transaction cash flows, infers documented missing
# history assumptions when current positions are not fully covered by observed
# transactions, calculates annualized XIRR, simple return, and chained Modified
# Dietz time-weighted return by currency.

from __future__ import annotations

import math
from datetime import date

import pandas as pd


def normalize_transaction_cash_flows(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Return dated investor cash flows by currency; buys are outflows, sells inflows."""
    if transactions_df.empty:
        return pd.DataFrame(columns=["transaction_date", "currency", "cash_flow"])

    flows = transactions_df.copy()
    flows["transaction_date"] = pd.to_datetime(flows["transaction_date"], errors="coerce")
    flows["amount"] = pd.to_numeric(flows["transaction_amount"], errors="coerce")
    flows = flows.dropna(subset=["transaction_date", "amount"])
    if flows.empty:
        return pd.DataFrame(columns=["transaction_date", "currency", "cash_flow"])

    if "price_currency" in flows.columns:
        flows["currency"] = flows["price_currency"].fillna("").astype(str).str.strip().str.upper()
    else:
        flows["currency"] = ""

    transaction_type = (
        flows["transaction_type"].astype(str).str.strip().str.lower()
        if "transaction_type" in flows.columns
        else pd.Series("", index=flows.index)
    )
    is_buy = transaction_type.eq("buy")
    is_sell = transaction_type.eq("sell")
    flows["cash_flow"] = flows["amount"]
    flows.loc[is_buy, "cash_flow"] = -flows.loc[is_buy, "amount"].abs()
    flows.loc[is_sell, "cash_flow"] = flows.loc[is_sell, "amount"].abs()
    other_rows = ~(is_buy | is_sell)
    flows.loc[other_rows, "cash_flow"] = flows.loc[other_rows, "amount"]

    return (
        flows.groupby(["transaction_date", "currency"], as_index=False)["cash_flow"]
        .sum()
        .sort_values(["transaction_date", "currency"], ignore_index=True)
    )


def calculate_xirr_annualized(cash_flow_dates: list[pd.Timestamp], cash_flows: list[float]) -> float | None:
    """Calculate annualized IRR (XIRR) from dated cash flows using bisection."""
    if len(cash_flows) < 2 or len(cash_flow_dates) != len(cash_flows):
        return None
    if not any(flow < 0 for flow in cash_flows) or not any(flow > 0 for flow in cash_flows):
        return None

    base_date = min(cash_flow_dates)
    year_fractions = [
        (flow_date - base_date).days / 365.2425 for flow_date in cash_flow_dates
    ]

    def npv(rate: float) -> float:
        if rate <= -1.0:
            return math.inf

        total = 0.0
        try:
            log_growth = math.log1p(rate)
        except ValueError:
            return math.inf

        for flow, years in zip(cash_flows, year_fractions):
            try:
                discount = math.exp(years * log_growth)
            except OverflowError:
                return math.copysign(math.inf, flow)
            if discount == 0:
                return math.copysign(math.inf, flow)
            total += flow / discount
        return total

    grid_rates = [
        -0.9999,
        -0.95,
        -0.9,
        -0.75,
        -0.5,
        -0.25,
        -0.1,
        -0.05,
        0.0,
        0.05,
        0.1,
        0.2,
        0.3,
        0.5,
        0.75,
        1.0,
        1.5,
        2.0,
        3.0,
        5.0,
        10.0,
    ]
    low = None
    high = None
    low_npv = None
    high_npv = None
    previous_rate = None
    previous_npv = None
    for rate in grid_rates:
        current_npv = npv(rate)
        if not math.isfinite(current_npv):
            previous_rate = rate
            previous_npv = current_npv
            continue
        if current_npv == 0:
            return rate
        if (
            previous_rate is not None
            and previous_npv is not None
            and math.isfinite(previous_npv)
            and previous_npv * current_npv < 0
        ):
            low = previous_rate
            high = rate
            low_npv = previous_npv
            high_npv = current_npv
            break
        previous_rate = rate
        previous_npv = current_npv

    if low is None or high is None or low_npv is None or high_npv is None:
        return None

    for _ in range(200):
        mid = (low + high) / 2.0
        mid_npv = npv(mid)
        if not math.isfinite(mid_npv):
            return None
        if abs(mid_npv) < 1e-8:
            return mid
        if low_npv * mid_npv <= 0:
            high = mid
            high_npv = mid_npv
        else:
            low = mid
            low_npv = mid_npv

    return (low + high) / 2.0


def calculate_portfolio_performance_metrics(
    transactions_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    monthly_position_totals_df: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Calculate IRR, simple return, and TWR without blending unlike currencies."""
    empty_metrics = {
        "annualized_irr": None,
        "cagr": None,
        "simple_return": None,
        "time_weighted_return": None,
        "assumptions": [],
        "by_currency": {},
        "by_holding": [],
    }
    if transactions_df.empty and positions_df.empty:
        return empty_metrics

    daily_flows = normalize_transaction_cash_flows(transactions_df)

    if positions_df.empty:
        ending_values = pd.Series(dtype="float64")
        cost_basis_values = pd.Series(dtype="float64")
    else:
        positions = positions_df.copy()
        positions["currency"] = positions["currency"].fillna("").astype(str).str.strip().str.upper()
        positions["market_value"] = pd.to_numeric(positions["market_value"], errors="coerce").fillna(0)
        if "total_cost" not in positions.columns:
            positions["total_cost"] = 0.0
        positions["total_cost"] = pd.to_numeric(positions["total_cost"], errors="coerce").fillna(0)
        ending_values = positions.groupby("currency")["market_value"].sum()
        cost_basis_values = positions.groupby("currency")["total_cost"].sum()

    currencies = sorted(
        set(daily_flows["currency"].dropna().astype(str))
        | set(ending_values.index.astype(str))
    )
    currencies = [currency for currency in currencies if currency]
    if not currencies:
        return empty_metrics

    valuation_points = build_monthly_valuation_points(
        monthly_position_totals_df, ending_values
    )

    by_currency: dict[str, dict[str, object]] = {}
    for currency in currencies:
        currency_flows = daily_flows[daily_flows["currency"] == currency]
        ending_value = float(ending_values.get(currency, 0.0))

        total_outflows = float(-currency_flows.loc[
            currency_flows["cash_flow"] < 0, "cash_flow"
        ].sum())
        total_inflows = float(currency_flows.loc[
            currency_flows["cash_flow"] > 0, "cash_flow"
        ].sum())
        cost_basis = float(cost_basis_values.get(currency, 0.0))
        currency_valuations = valuation_points[valuation_points["currency"] == currency]
        assumption = build_missing_history_assumption(
            currency,
            currency_flows,
            currency_valuations,
            cost_basis,
            total_outflows,
            total_inflows,
        )
        assumed_initial_outflow = float(assumption["amount"])
        adjusted_outflows = total_outflows + assumed_initial_outflow
        simple_return = None
        if adjusted_outflows > 0:
            simple_return = float(
                (ending_value + total_inflows - adjusted_outflows)
                / adjusted_outflows
            )
        cagr = calculate_cagr(
            adjusted_outflows=adjusted_outflows,
            ending_value=ending_value,
            total_inflows=total_inflows,
            flows_df=currency_flows,
            assumed_start_date=assumption["date"] if assumed_initial_outflow > 0 else None,
        )

        assumptions: list[str] = []
        return_flows = currency_flows.copy()
        if assumed_initial_outflow > 0:
            return_flows = pd.concat(
                [
                    pd.DataFrame(
                        [
                            {
                                "transaction_date": assumption["date"],
                                "currency": currency,
                                "cash_flow": -assumed_initial_outflow,
                            }
                        ]
                    ),
                    return_flows,
                ],
                ignore_index=True,
            ).sort_values("transaction_date", ignore_index=True)
            assumptions.append(format_missing_history_assumption(assumption))

        irr_annualized = None
        if not return_flows.empty:
            cash_flow_dates = return_flows["transaction_date"].tolist()
            cash_flows = return_flows["cash_flow"].tolist()
            cash_flow_dates.append(pd.Timestamp(date.today()))
            cash_flows.append(ending_value)
            irr_annualized = calculate_xirr_annualized(cash_flow_dates, cash_flows)

        time_weighted_return = calculate_time_weighted_return(
            return_flows,
            currency_valuations,
        )

        by_currency[currency] = {
            "annualized_irr": irr_annualized,
            "cagr": cagr,
            "simple_return": simple_return,
            "time_weighted_return": time_weighted_return,
            "data_basis": "assumption" if assumed_initial_outflow > 0 else "reported",
            "assumptions": assumptions,
        }

    all_assumptions = [
        assumption
        for currency_metrics in by_currency.values()
        for assumption in currency_metrics["assumptions"]
    ]
    metrics = empty_metrics | {
        "assumptions": all_assumptions,
        "by_currency": by_currency,
        "by_holding": calculate_holding_performance_metrics(
            transactions_df,
            positions_df,
        ),
    }
    if len(by_currency) == 1:
        only_metrics = next(iter(by_currency.values()))
        metrics.update(only_metrics)
    return metrics


def calculate_holding_performance_metrics(
    transactions_df: pd.DataFrame,
    positions_df: pd.DataFrame,
) -> list[dict[str, object]]:
    """Calculate per-holding IRR, simple return, and TWR for current positions."""
    if positions_df.empty:
        return []

    positions = positions_df.copy()
    positions["stock_name"] = positions["stock_name"].fillna("").astype(str).str.strip()
    positions["stock_code"] = positions["stock_code"].fillna("").astype(str).str.strip().str.upper()
    positions["currency"] = positions["currency"].fillna("").astype(str).str.strip().str.upper()
    positions["market_value"] = pd.to_numeric(positions["market_value"], errors="coerce").fillna(0.0)
    positions["total_cost"] = pd.to_numeric(positions.get("total_cost", 0.0), errors="coerce").fillna(0.0)
    positions = positions[(positions["stock_name"] != "") | (positions["stock_code"] != "")]
    if positions.empty:
        return []

    positions["holding_key"] = positions["stock_code"]
    missing_code_mask = positions["holding_key"] == ""
    positions.loc[missing_code_mask, "holding_key"] = (
        "__NAME__" + positions.loc[missing_code_mask, "stock_name"].str.upper()
    )
    grouped_positions = (
        positions.groupby(["holding_key", "stock_code", "stock_name", "currency"], as_index=False)[
            ["market_value", "total_cost"]
        ]
        .sum()
    )

    if transactions_df.empty:
        holding_flows = pd.DataFrame(
            columns=["holding_key", "currency", "transaction_date", "cash_flow"]
        )
    else:
        transactions = transactions_df.copy()
        transactions["stock_name"] = transactions["stock_name"].fillna("").astype(str).str.strip()
        transactions["stock_code"] = transactions["stock_code"].fillna("").astype(str).str.strip().str.upper()
        transactions["price_currency"] = (
            transactions["price_currency"].fillna("").astype(str).str.strip().str.upper()
        )
        transactions["transaction_date"] = pd.to_datetime(
            transactions["transaction_date"], errors="coerce"
        )
        transactions["transaction_amount"] = pd.to_numeric(
            transactions["transaction_amount"], errors="coerce"
        )
        transaction_type = transactions["transaction_type"].astype(str).str.strip().str.lower()
        transactions = transactions.dropna(subset=["transaction_date", "transaction_amount"])
        transactions["cash_flow"] = transactions["transaction_amount"]
        buy_mask = transaction_type.eq("buy")
        sell_mask = transaction_type.eq("sell")
        transactions.loc[buy_mask, "cash_flow"] = -transactions.loc[buy_mask, "transaction_amount"].abs()
        transactions.loc[sell_mask, "cash_flow"] = transactions.loc[sell_mask, "transaction_amount"].abs()

        transactions["holding_key"] = transactions["stock_code"]
        missing_tx_code_mask = transactions["holding_key"] == ""
        transactions.loc[missing_tx_code_mask, "holding_key"] = (
            "__NAME__" + transactions.loc[missing_tx_code_mask, "stock_name"].str.upper()
        )
        holding_flows = (
            transactions.groupby(
                ["holding_key", "price_currency", "transaction_date"], as_index=False
            )["cash_flow"]
            .sum()
            .rename(columns={"price_currency": "currency"})
            .sort_values(["holding_key", "currency", "transaction_date"], ignore_index=True)
        )

    rows: list[dict[str, object]] = []
    for _, holding in grouped_positions.iterrows():
        holding_key = str(holding["holding_key"])
        currency = str(holding["currency"])
        ending_value = float(holding["market_value"])
        cost_basis = float(holding["total_cost"])
        flow_rows = holding_flows[
            (holding_flows["holding_key"] == holding_key)
            & (holding_flows["currency"] == currency)
        ].copy()

        total_outflows = float(-flow_rows.loc[flow_rows["cash_flow"] < 0, "cash_flow"].sum())
        total_inflows = float(flow_rows.loc[flow_rows["cash_flow"] > 0, "cash_flow"].sum())
        assumption = build_missing_history_assumption(
            currency=currency,
            currency_flows=flow_rows,
            currency_valuations=pd.DataFrame(
                [{"month": pd.Timestamp(date.today()).normalize(), "currency": currency, "ending_value": ending_value}]
            ),
            cost_basis=cost_basis,
            total_outflows=total_outflows,
            total_inflows=total_inflows,
        )
        assumed_initial_outflow = float(assumption["amount"])
        adjusted_outflows = total_outflows + assumed_initial_outflow
        simple_return = None
        if adjusted_outflows > 0:
            simple_return = float(
                (ending_value + total_inflows - adjusted_outflows) / adjusted_outflows
            )
        cagr = calculate_cagr(
            adjusted_outflows=adjusted_outflows,
            ending_value=ending_value,
            total_inflows=total_inflows,
            flows_df=flow_rows,
            assumed_start_date=assumption["date"] if assumed_initial_outflow > 0 else None,
        )

        return_flows = flow_rows
        if assumed_initial_outflow > 0:
            return_flows = pd.concat(
                [
                    pd.DataFrame(
                        [
                            {
                                "transaction_date": assumption["date"],
                                "currency": currency,
                                "cash_flow": -assumed_initial_outflow,
                            }
                        ]
                    ),
                    flow_rows,
                ],
                ignore_index=True,
            ).sort_values("transaction_date", ignore_index=True)

        irr_annualized = None
        if not return_flows.empty:
            cash_flow_dates = return_flows["transaction_date"].tolist()
            cash_flows = return_flows["cash_flow"].tolist()
            cash_flow_dates.append(pd.Timestamp(date.today()))
            cash_flows.append(ending_value)
            irr_annualized = calculate_xirr_annualized(cash_flow_dates, cash_flows)

        twr = calculate_time_weighted_return(
            return_flows,
            pd.DataFrame(
                [{"month": pd.Timestamp(date.today()).normalize(), "ending_value": ending_value}]
            ),
        )
        rows.append(
            {
                "stock_code": str(holding["stock_code"]),
                "stock_name": str(holding["stock_name"]),
                "currency": currency,
                "annualized_irr": irr_annualized,
                "cagr": cagr,
                "simple_return": simple_return,
                "time_weighted_return": twr,
                "assumption_note": (
                    "Incomplete history; initial investment inferred"
                    if assumed_initial_outflow > 0
                    else ""
                ),
            }
        )

    return sorted(rows, key=lambda row: (row["stock_name"], row["stock_code"]))


def build_missing_history_assumption(
    currency: str,
    currency_flows: pd.DataFrame,
    currency_valuations: pd.DataFrame,
    cost_basis: float,
    total_outflows: float,
    total_inflows: float,
) -> dict[str, object]:
    """Infer any missing starting capital from available position and flow data."""
    missing_cost_basis = max(cost_basis + total_inflows - total_outflows, 0.0)
    assumption_date, date_source = infer_assumed_initial_flow_date(
        currency_flows, currency_valuations
    )
    return {
        "currency": currency,
        "amount": missing_cost_basis,
        "date": assumption_date,
        "date_source": date_source,
        "cost_basis": cost_basis,
        "observed_buy_outflows": total_outflows,
        "observed_sell_inflows": total_inflows,
    }


def calculate_cagr(
    adjusted_outflows: float,
    ending_value: float,
    total_inflows: float,
    flows_df: pd.DataFrame,
    assumed_start_date: pd.Timestamp | None = None,
) -> float | None:
    """Calculate CAGR from total-return multiple and elapsed years."""
    if adjusted_outflows <= 0:
        return None

    ending_wealth = ending_value + total_inflows
    if ending_wealth <= 0:
        return None

    start_date: pd.Timestamp | None = None
    if assumed_start_date is not None:
        start_date = pd.Timestamp(assumed_start_date)
    elif not flows_df.empty:
        start_date = pd.Timestamp(flows_df["transaction_date"].min())

    if start_date is None:
        return None

    end_date = pd.Timestamp(date.today())
    elapsed_years = (end_date - start_date).days / 365.2425
    if elapsed_years <= 0:
        return None

    total_return_multiple = ending_wealth / adjusted_outflows
    if total_return_multiple <= 0:
        return None
    return float(total_return_multiple ** (1.0 / elapsed_years) - 1.0)


def infer_assumed_initial_flow_date(
    currency_flows: pd.DataFrame, currency_valuations: pd.DataFrame
) -> tuple[pd.Timestamp, str]:
    """Infer the best available date for missing starting capital."""
    candidate_dates: list[pd.Timestamp] = []
    if not currency_flows.empty:
        candidate_dates.append(currency_flows["transaction_date"].min())
    if not currency_valuations.empty:
        candidate_dates.append(currency_valuations["month"].min())

    if candidate_dates:
        earliest_date = min(pd.Timestamp(candidate) for candidate in candidate_dates)
        if (
            not currency_valuations.empty
            and earliest_date == pd.Timestamp(currency_valuations["month"].min())
        ):
            return earliest_date, "earliest available month-end position snapshot"
        return (
            earliest_date - pd.Timedelta(days=1),
            "day before earliest observed transaction",
        )

    return (
        pd.Timestamp(date.today()) - pd.DateOffset(years=1),
        "one year before report date because no transactions or valuations were available",
    )


def format_missing_history_assumption(assumption: dict[str, object]) -> str:
    """Create the web-facing assumption text from the inferred data."""
    currency = assumption["currency"]
    amount = float(assumption["amount"])
    assumed_date = pd.Timestamp(assumption["date"]).date().isoformat()
    return (
        f"{currency}: transaction history is incomplete. Based on current cost "
        f"basis {currency} {float(assumption['cost_basis']):,.2f}, observed buys "
        f"{currency} {float(assumption['observed_buy_outflows']):,.2f}, and "
        f"observed sells {currency} {float(assumption['observed_sell_inflows']):,.2f}, "
        f"assumed an initial {currency} {amount:,.2f} investment on {assumed_date} "
        f"({assumption['date_source']})."
    )


def build_monthly_valuation_points(
    monthly_position_totals_df: pd.DataFrame | None, ending_values: pd.Series
) -> pd.DataFrame:
    """Build month-end valuation points by currency from available position snapshots."""
    columns = ["month", "currency", "ending_value"]
    if monthly_position_totals_df is None or monthly_position_totals_df.empty:
        valuations = pd.DataFrame(columns=columns)
    else:
        valuations = monthly_position_totals_df.copy()
        valuations["month"] = (
            pd.to_datetime(valuations["month"], errors="coerce")
            .dt.to_period("M")
            .dt.to_timestamp("M")
        )
        valuations["currency"] = (
            valuations["series"].astype(str).str.rsplit(" - ", n=1).str[-1].str.upper()
        )
        valuations["ending_value"] = pd.to_numeric(
            valuations["market_value"], errors="coerce"
        ).fillna(0)
        valuations = (
            valuations.dropna(subset=["month"])
            .groupby(["month", "currency"], as_index=False)["ending_value"]
            .sum()
        )

    current_month = pd.Timestamp(date.today()).normalize()
    current_rows = pd.DataFrame(
        [
            {
                "month": current_month,
                "currency": str(currency),
                "ending_value": float(value),
            }
            for currency, value in ending_values.items()
        ]
    )
    if current_rows.empty:
        return valuations[columns]

    valuations = pd.concat([valuations, current_rows], ignore_index=True)
    return (
        valuations.sort_values("month")
        .drop_duplicates(["month", "currency"], keep="last")
        .sort_values(["currency", "month"], ignore_index=True)[columns]
    )


def calculate_time_weighted_return(
    currency_flows: pd.DataFrame, currency_valuations: pd.DataFrame
) -> float | None:
    """Approximate TWR with Modified Dietz sub-period returns between valuations."""
    if currency_flows.empty or currency_valuations.empty:
        return None

    flows = currency_flows.copy()
    flows["transaction_date"] = pd.to_datetime(
        flows["transaction_date"], errors="coerce"
    )
    flows["external_flow"] = -pd.to_numeric(flows["cash_flow"], errors="coerce")
    flows = flows.dropna(subset=["transaction_date", "external_flow"]).sort_values(
        "transaction_date", ignore_index=True
    )
    if flows.empty:
        return None

    valuations = currency_valuations[["month", "ending_value"]].copy()
    valuations["valuation_date"] = pd.to_datetime(valuations["month"], errors="coerce")
    valuations["ending_value"] = pd.to_numeric(
        valuations["ending_value"], errors="coerce"
    )
    valuations = (
        valuations.dropna(subset=["valuation_date", "ending_value"])
        .sort_values("valuation_date")
        .drop_duplicates("valuation_date", keep="last")
        .reset_index(drop=True)
    )
    if valuations.empty:
        return None

    growth_factor = 1.0
    beginning_value = 0.0
    previous_valuation_date: pd.Timestamp | None = None
    calculated_periods = 0

    for _, row in valuations.iterrows():
        valuation_date = pd.Timestamp(row["valuation_date"])
        month_end_value = float(row["ending_value"])

        if previous_valuation_date is None:
            period_flows = flows[flows["transaction_date"] <= valuation_date]
            if period_flows.empty:
                beginning_value = month_end_value
                previous_valuation_date = valuation_date
                continue
            period_start_date = period_flows["transaction_date"].min()
        else:
            period_flows = flows[
                (flows["transaction_date"] > previous_valuation_date)
                & (flows["transaction_date"] <= valuation_date)
            ]
            period_start_date = previous_valuation_date

        period_return = calculate_modified_dietz_period_return(
            beginning_value,
            month_end_value,
            period_flows,
            period_start_date,
            valuation_date,
        )
        if period_return is None:
            beginning_value = month_end_value
            previous_valuation_date = valuation_date
            continue

        growth_factor *= 1.0 + period_return
        calculated_periods += 1
        beginning_value = month_end_value
        previous_valuation_date = valuation_date

    if calculated_periods == 0 or growth_factor <= 0:
        return None
    return growth_factor - 1.0


def calculate_modified_dietz_period_return(
    beginning_value: float,
    ending_value: float,
    period_flows: pd.DataFrame,
    period_start_date: pd.Timestamp,
    period_end_date: pd.Timestamp,
) -> float | None:
    """Calculate one sub-period return using date-weighted external flows."""
    period_flow_total = float(period_flows["external_flow"].sum())
    period_days = max((period_end_date - period_start_date).days, 1)
    weighted_flow_total = 0.0
    for _, flow in period_flows.iterrows():
        days_remaining = max((period_end_date - flow["transaction_date"]).days, 0)
        weight = days_remaining / period_days
        weighted_flow_total += float(flow["external_flow"]) * weight

    denominator = beginning_value + weighted_flow_total
    if denominator <= 0:
        return None

    return (ending_value - beginning_value - period_flow_total) / denominator
