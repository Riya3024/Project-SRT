"""
Project SRT — shared contract-serialization helper.

Several frozen contracts mark a field optional (not in `required`) without
declaring `null` as an allowed type for it — e.g. `incident.schema.json`'s
`tenant_id` is plain `{"type": "string"}`, not `["string", "null"]`. A
dataclass default of `None` is a normal, honest Python representation of
"not set", but naively serializing that as JSON `null` violates such a
field's type constraint. Omitting the key entirely is valid either way, so
that's what this helper does for any field.
"""

from __future__ import annotations

import dataclasses
from typing import Any


def to_contract_dict(obj: Any) -> dict:
    """Serialize a dataclass to a dict, dropping keys whose value is None."""
    return {k: v for k, v in dataclasses.asdict(obj).items() if v is not None}
