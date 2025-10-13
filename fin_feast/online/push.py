from __future__ import annotations

from typing import Iterable

import pandas as pd
from feast import FeatureStore


def push_rows_to_online(
    store_repo_path: str, table_name: str, df: pd.DataFrame, entity_keys: Iterable[str]
) -> None:
    """Push rows directly to Feast online store.

    Tries multiple Feast API variants for write_to_online_store to support different versions.
    Assumes df has columns: symbol, event_timestamp and all FeatureView fields.
    """

    fs = FeatureStore(repo_path=store_repo_path)

    # Prepare rows as dicts including the entity key
    payloads = []
    for _, row in df.iterrows():
        rec = row.to_dict()
        # Ensure symbol is present as entity
        if "symbol" not in rec:
            raise ValueError("DataFrame must include 'symbol' column for online push")
        # event_timestamp is not required in online store payloads; drop it to avoid dtype issues
        rec.pop("event_timestamp", None)
        payloads.append(rec)

    last_err: Exception | None = None
    for rec in payloads:
        # Normalize NaNs to None for online store payloads
        for k, v in list(rec.items()):
            if isinstance(v, float) and (pd.isna(v)):
                rec[k] = None
        # Try several API signatures in order
        try:
            fs.write_to_online_store(table_name, rec)  # positional (older)
            continue
        except Exception as e:
            last_err = e
        try:
            fs.write_to_online_store(table=table_name, values=rec)  # keyword (older)
            continue
        except Exception as e:
            last_err = e
        try:
            fs.write_to_online_store(table_name, [rec])  # positional list
            continue
        except Exception as e:
            last_err = e
        try:
            fs.write_to_online_store(
                feature_view_name=table_name, entity_rows=[rec]
            )  # keyword (newer)
            continue
        except Exception as e:
            last_err = e
            # If all variants failed, raise the last error
            raise last_err
