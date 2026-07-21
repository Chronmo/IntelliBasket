"""Request models and response serialization helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from pydantic import BaseModel, Field


class MarketingRecommendationRequest(BaseModel):
    """Filters used to find segment-specific cross-sell rules."""

    segmentCode: str = Field(default="ALL", min_length=1, max_length=32)
    productCode: str = Field(min_length=1, max_length=64)
    minLift: float = Field(default=1.05, ge=0)
    limit: int = Field(default=10, ge=1, le=50)


def serializeValue(rawValue: Any) -> Any:
    """Convert ORM values into JSON-compatible primitives."""
    if isinstance(rawValue, Decimal):
        return float(rawValue)
    if isinstance(rawValue, (date, datetime)):
        return rawValue.isoformat()
    return rawValue


def serializeRecord(record: Any, fieldNames: list[str]) -> dict[str, Any]:
    """Serialize selected camelCase ORM attributes."""
    return {fieldName: serializeValue(getattr(record, fieldName)) for fieldName in fieldNames}


def buildSuccessResponse(
    request: Request,
    data: Any,
    **metadata: Any,
) -> dict[str, Any]:
    """Build the standard IntelliBasket success envelope."""
    return {
        "success": True,
        "data": data,
        "meta": {
            "requestId": request.state.requestId,
            "generatedAt": datetime.now(UTC).isoformat(),
            **metadata,
        },
    }
