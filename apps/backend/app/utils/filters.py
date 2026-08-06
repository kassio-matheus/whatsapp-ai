"""Helpers to build safe query filters from route query parameters.

Every list route exposes the schema attributes of its resource as query
parameters so records can be found directly, e.g.
``GET /whatsapp/contacts?name=Kássio`` or ``GET /whatsapp/conversations?phone=+5575997136619``.

``mapping`` entries describe how each parameter is applied:

* ``"column"`` — equality against the model column.
* ``("column", "contains")`` / ``("column", "startswith")`` — case-insensitive
  substring match (used for search-friendly text fields).
* a callable that receives the raw value and returns a SQLAlchemy condition.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import SQLModel

ConditionFactory = Callable[[Any], ColumnElement[Any]]


def build_conditions(
    model: type[SQLModel],
    mapping: dict[str, str | tuple[str, str] | ConditionFactory],
    **values: Any,
) -> list[ColumnElement[Any]]:
    """Return SQLAlchemy conditions for the non-empty ``values``.

    Parameters without a mapping entry are ignored, which keeps the filters
    explicit and safe (only model attributes can be filtered).
    """
    conditions: list[ColumnElement[Any]] = []
    for param, value in values.items():
        if value is None or value == "":
            continue
        spec = mapping.get(param)
        if spec is None:
            continue
        if callable(spec):
            condition = spec(value)
        elif isinstance(spec, str):
            condition = getattr(model, spec) == value
        else:
            column_name, mode = spec
            column = getattr(model, column_name)
            if mode == "contains":
                condition = column.ilike(f"%{value}%")
            elif mode == "startswith":
                condition = column.ilike(f"{value}%")
            else:
                condition = column == value
        conditions.append(condition)
    return conditions
