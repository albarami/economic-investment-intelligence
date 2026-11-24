"""Closed site_check projection; make_area owns all preset validation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eii_product.tools.make_area import validate_request


class Pin(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]


class Inputs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    activity: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=200)]
    lang: Literal["en", "ar"] = "en"
    pin: Pin | None = None
    shape_id: str | None = None
    mode: Literal["distance", "walk", "drive"] | None = None
    cutoff: int | None = None

    def area_request(self) -> dict[str, Any]:
        """Project the closed HTTP input onto the existing make_area grammar."""
        if "shape_id" in self.model_fields_set:
            return {"shape_id": self.shape_id}
        if self.pin is None:
            raise ValueError("INVALID_ARGUMENT")
        return {
            "latitude": self.pin.lat,
            "longitude": self.pin.lon,
            "mode": self.mode if "mode" in self.model_fields_set else "walk",
            "cutoff": self.cutoff if "cutoff" in self.model_fields_set else 5,
        }

    @model_validator(mode="after")
    def supported_area(self) -> Inputs:
        present = self.model_fields_set
        if "shape_id" in present and present & {"pin", "mode", "cutoff"}:
            raise ValueError("INVALID_ARGUMENT")
        if ("mode" in present) != ("cutoff" in present):
            raise ValueError("INVALID_ARGUMENT")
        validate_request(self.area_request(), "site_check")
        if self.activity.isdigit() and len(self.activity) in {8, 11}:
            raise ValueError("INVALID_ARGUMENT")
        return self
