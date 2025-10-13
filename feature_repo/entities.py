from __future__ import annotations

from feast import Entity
from feast.value_type import ValueType

# Explicitly set value_type to ensure proper inference for join key
symbol = Entity(name="symbol", join_keys=["symbol"], value_type=ValueType.STRING)
