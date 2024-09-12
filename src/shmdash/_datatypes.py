from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from datetime import datetime


class AttributeType(str, Enum):
    DATETIME = "dateTime"
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"

    def __str__(self) -> str:
        return self.value


class DiagramScale(str, Enum):
    LIN = "lin"
    LOG = "log"

    def __str__(self) -> str:
        return self.value


def _remove_none_values(dct: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in dct.items() if v is not None}


@dataclass
class Attribute:
    """
    Attribute / channel definition.

    Data structure for the JSON/dict representation:
    {
        "AbsDateTime": {
            "descr": "Absolutetime in ISO8601, UTC Zone (max. μs)",
            "unit": None,
            "type": "dateTime",
            "format": "YYYY-MM-DDThh:mm:ss[.ssssss]Z",
            "softLimits": [0, None],
            "diagramScale": "lin",
        }
    }
    """

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 chars)
    desc: str | None  #: Channel description
    unit: str | None  #: Measurement unit
    type: AttributeType  #: Type
    format: str | None = None  #: Format string, e.g. %s for str, %d for int, %.2f for float
    soft_limits: tuple[float | None, float | None] | None = None  #: Min/max values
    diagram_scale: DiagramScale | None = None  #: Diagram scale

    @classmethod
    def from_dict(cls, identifier: str, fields: dict[str, Any]) -> Attribute:
        """Create `Attribute` from parsed JSON dict."""

        return cls(
            identifier=identifier,
            desc=fields.get("descr"),
            unit=fields.get("unit"),
            type=AttributeType(fields["type"]),
            format=fields.get("format"),
            soft_limits=fields.get("softLimits"),
            diagram_scale=(
                DiagramScale(fields["diagramScale"]) if "diagramScale" in fields else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert into dict for JSON representation."""
        return _remove_none_values(
            {
                "descr": self.desc,
                "unit": self.unit,
                "type": str(self.type),
                "format": self.format,
                "softLimits": self.soft_limits,
                "diagramScale": str(self.diagram_scale) if self.diagram_scale else None,
            }
        )


@dataclass
class VirtualChannel:
    """
    Virtual channel / channel group definition.

    Data structure for the JSON/dict representation:
    "1": {
        "name": "Control Signal",
        "descr": "Control signal voltage",
        "attributes": ["AbsDateTime", "DSET", "VOLTAGE"],
        "prop": ["STREAM", "PAR"]
    }
    """

    identifier: str  #: Unique identifier (alphanumeric and "_", max. 32 chars), VAE requires int
    name: str | None  #: Channel group name
    desc: str | None  #: Channel group description
    #: List of assigned attribute / channel identifiers.
    #: Following channels have specific meaning: AbsDateTime, DSET, X, Y
    #: Following statistics can be applied:
    #: min(id), max(id), avg(id), sum(id), stdDev(id), nbVals(id), var(id), deltaT()
    attributes: list[str]
    #: Properties used for interpretation of the data (must contain at least 1 item):
    #: - hardcoded on the server side: STREAM, LOC (require X, Y), STAT (statistics)
    #: - used in VAE: HIT, PAR, ...
    #: Use for example: [STREAM, HIT]
    properties: list[str] | None = None

    @classmethod
    def from_dict(cls, identifier: str, fields: dict[str, Any]) -> VirtualChannel:
        """Create `VirtualChannel` from parsed JSON dict."""
        return cls(
            identifier=str(identifier),
            name=fields.get("name"),
            desc=fields.get("descr"),
            attributes=fields["attributes"],
            properties=fields.get("prop"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert into dict for JSON representation."""
        return _remove_none_values(
            {
                "name": self.name,
                "descr": self.desc,
                "attributes": self.attributes,
                "prop": self.properties,
            }
        )


@dataclass
class Setup:
    """Setup."""

    attributes: list[Attribute]  #: List of attributes
    virtual_channels: list[VirtualChannel]  #: List of virtual channels

    def is_empty(self) -> bool:
        """Check if the setup is empty."""
        return not self.attributes and not self.virtual_channels

    @classmethod
    def from_dict(cls, setup_dict: dict[str, Any]) -> Setup:
        return cls(
            attributes=[
                Attribute.from_dict(identifier, fields)
                for identifier, fields in setup_dict.get("attributes", {}).items()
            ],
            virtual_channels=[
                VirtualChannel.from_dict(identifier, fields)
                for identifier, fields in setup_dict.get("virtual_channels", {}).items()
            ],
        )

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "attributes": {attr.identifier: attr.to_dict() for attr in self.attributes},
            "virtual_channels": {vc.identifier: vc.to_dict() for vc in self.virtual_channels},
        }


@dataclass
class UploadData:
    """Upload data."""

    timestamp: datetime  #: Absolute datetime (unique!)
    #: List of values in order of the virtual channel attributes
    data: Sequence[int | float | str]
