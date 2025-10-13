from __future__ import annotations

from typing import Iterable

import pandas as pd
from feast import FeatureStore


def push_rows_to_online(store_repo_path: str, table_name: str, df: pd.DataFrame, entity_keys: Iterable[str]) -> None:
    """Push rows directly to Feast online store.

    This uses write_to_online_store by creating an entity keyed DataFrame.
    Assumes df has columns: symbol, event_timestamp and all FeatureView fields.
    """

    fs = FeatureStore(repo_path=store_repo_path)

    # Feast write_to_online_store expects {entity_name: keys} mapping with a dict of feature values
    # Simpler approach: convert df to a list of dicts and write via online write API
    # Here, we leverage write_to_online_store by constructing an appropriate dict
    rows = []
    for _, row in df.iterrows():
        features = row.drop(labels=["symbol"]).to_dict()
        rows.append((row["symbol"], features))

    # In absence of a bulk push shortcut, do a small loop
    for symbol, features in rows:
        fs.write_to_online_store(
            table=table_name,
            values={
                "symbol": symbol,
                **features,
            },
        )
