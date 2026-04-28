from __future__ import annotations

import pandas as pd


def print_duplicate_records_message(dataframe_name: str, dataframe: pd.DataFrame) -> None:
    """Print duplicate full-row records for a dataframe, if any exist."""
    duplicate_records = dataframe[dataframe.duplicated(keep=False)]
    if duplicate_records.empty:
        return

    print(
        f"\nDuplicate records found in {dataframe_name}: "
        f"{len(duplicate_records)} duplicated row(s)."
    )
    print(duplicate_records.to_string(index=False))
