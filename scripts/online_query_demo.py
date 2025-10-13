from __future__ import annotations

import argparse
import os
from feast import FeatureStore
from feast.errors import FeatureViewNotFoundException

from feast_polygon_poc.logging import get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--with-odfv", action="store_true", default=os.getenv("FEAST_ENABLE_ODFV") == "1",
                   help="Include on-demand (derived_stateless_fv) features if available")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    fs = FeatureStore(repo_path="feature_repo")

    minute_features = [
        "minute_ohlcv_fv:open",
        "minute_ohlcv_fv:high",
        "minute_ohlcv_fv:low",
        "minute_ohlcv_fv:close",
        "minute_ohlcv_fv:vwap",
        "minute_ohlcv_fv:volume",
        "minute_ohlcv_fv:return_1",
        "minute_ohlcv_fv:ma_5",
        "minute_ohlcv_fv:ma_20",
        "minute_ohlcv_fv:vol_20",
        "minute_ohlcv_fv:rsi_14",
        "minute_ohlcv_fv:atr_14",
    ]
    odfv_features = [
        "derived_stateless_fv:hlc3",
        "derived_stateless_fv:ohlc4",
        "derived_stateless_fv:vol_log",
        "derived_stateless_fv:spread",
        "derived_stateless_fv:body",
        "derived_stateless_fv:vwap_premium",
    ]

    feature_refs = minute_features + (odfv_features if args.with_odfv else [])

    entities = [{"symbol": s} for s in args.symbols]

    try:
        res = fs.get_online_features(features=feature_refs, entity_rows=entities).to_dict()
    except FeatureViewNotFoundException as e:
        logger.warning("%s. Retrying without ODFV features.", e)
        res = fs.get_online_features(features=minute_features, entity_rows=entities).to_dict()

    # Pretty print per symbol
    fields = res.keys()
    for i, s in enumerate(args.symbols):
        logger.info("Symbol=%s", s)
        for f in fields:
            logger.info("  %s: %s", f, res[f][i])


if __name__ == "__main__":
    main()
