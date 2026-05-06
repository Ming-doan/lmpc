from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class PlatformOut(BaseModel):
    id: int
    name: str
    display_name: str | None
    adapter_class: str | None
    default_image: str | None
    default_port: int | None
    description: str | None

    model_config = {"from_attributes": True}


class ModelOut(BaseModel):
    id: int
    name: str
    hf_id: str | None
    size_b: Decimal | None
    quantization: str | None
    context_length: int | None

    model_config = {"from_attributes": True}


class ModelCreate(BaseModel):
    name: str
    hf_id: str | None = None
    size_b: Decimal | None = None
    quantization: str | None = None
    context_length: int | None = None
    metadata_: dict[str, Any] | None = None


class PromptSetOut(BaseModel):
    id: int
    name: str
    description: str | None
    version: int

    model_config = {"from_attributes": True}
