from __future__ import annotations

from feast import Entity

# Value type not strictly required in newer Feast; join_key is sufficient
symbol = Entity(name="symbol", join_keys=["symbol"]) 
