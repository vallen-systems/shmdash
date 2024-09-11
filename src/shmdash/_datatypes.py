from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterator, Sequence

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
    def from_dict(cls, attributes_dict: dict[str, dict[str, Any]]) -> Iterator[Attribute]:
        """Create `Attribute` from parsed JSON dict."""
        for identifier, dct in attributes_dict.items():
            yield cls(
                identifier=identifier,
                desc=dct.get("descr"),
                unit=dct.get("unit"),
                type=AttributeType(dct["type"]),
                format=dct.get("format"),
                soft_limits=dct.get("softLimits"),
                diagram_scale=DiagramScale(dct["diagramScale"]) if "diagramScale" in dct else None,
            )

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Convert into dict for JSON representation."""
        return {
            self.identifier: _remove_none_values(
                {
                    "descr": self.desc,
                    "unit": self.unit,
                    "type": str(self.type),
                    "format": self.format,
                    "softLimits": self.soft_limits,
                    "diagramScale": str(self.diagram_scale) if self.diagram_scale else None,
                }
            )
        }


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
    def from_dict(cls, attributes_dict: dict[str, dict[str, Any]]) -> Iterator[VirtualChannel]:
        """Create `VirtualChannel` from parsed JSON dict."""
        for identifier, dct in attributes_dict.items():
            yield cls(
                identifier=str(identifier),
                name=dct.get("name"),
                desc=dct.get("descr"),
                attributes=dct["attributes"],
                properties=dct.get("prop"),
            )

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Convert into dict for JSON representation."""
        return {
            self.identifier: _remove_none_values(
                {
                    "name": self.name,
                    "descr": self.desc,
                    "attributes": self.attributes,
                    "prop": self.properties,
                }
            )
        }


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
            attributes=list(Attribute.from_dict(setup_dict.get("attributes", {}))),
            virtual_channels=list(VirtualChannel.from_dict(setup_dict.get("virtual_channels", {}))),
        )

    def to_dict(self) -> dict[str, dict[str, Any]]:
        def _merge_dicts(*dcts):
            result = {}
            for dct in dcts:
                result.update(dct)
            return result

        return {
            "attributes": _merge_dicts(*(attr.to_dict() for attr in self.attributes)),
            "virtual_channels": _merge_dicts(*(vch.to_dict() for vch in self.virtual_channels)),
        }


@dataclass
class UploadData:
    """Upload data."""

    timestamp: datetime  #: Absolute datetime (unique!)
    #: List of values in order of the virtual channel attributes
    data: Sequence[int | float | str]
