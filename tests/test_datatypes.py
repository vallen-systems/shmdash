from shmdash import Attribute, AttributeType, DiagramScale, Setup, VirtualChannel


def test_attribute():
    attribute_dict = {
        "descr": "Description",
        "unit": "Unit",
        "type": "float32",
        "format": "%.2f",
        "softLimits": (0, None),
        "diagramScale": "lin",
    }
    attribute = Attribute.from_dict("Identifier", attribute_dict)

    assert attribute.identifier == "Identifier"
    assert attribute.desc == "Description"
    assert attribute.unit == "Unit"
    assert attribute.type == AttributeType.FLOAT32
    assert attribute.format == "%.2f"
    assert attribute.soft_limits == (0, None)
    assert attribute.diagram_scale == DiagramScale.LIN

    assert attribute.to_dict() == attribute_dict


def test_attribute_minimal():
    attribute_dict = {"type": "float32"}
    attribute = Attribute.from_dict("Identifier", attribute_dict)

    assert attribute.identifier == "Identifier"
    assert attribute.desc is None
    assert attribute.unit is None
    assert attribute.type == AttributeType.FLOAT32
    assert attribute.format is None
    assert attribute.soft_limits is None
    assert attribute.diagram_scale is None

    assert attribute.to_dict() == attribute_dict


def test_virtual_channel():
    virtual_channel_dict = {
        "name": "Name",
        "descr": "Description",
        "attributes": ["AbsDateTime", "DSET", "A"],
        "prop": ["STREAM", "HIT"],
    }
    virtual_channel = VirtualChannel.from_dict("Identifier", virtual_channel_dict)

    assert virtual_channel.identifier == "Identifier"
    assert virtual_channel.name == "Name"
    assert virtual_channel.desc == "Description"
    assert virtual_channel.attributes == ["AbsDateTime", "DSET", "A"]
    assert virtual_channel.properties == ["STREAM", "HIT"]

    assert virtual_channel.to_dict() == virtual_channel_dict


def test_virtual_channel_minimal():
    virtual_channel_dict = {"attributes": ["AbsDateTime", "DSET", "A"]}
    virtual_channel = VirtualChannel.from_dict("Identifier", virtual_channel_dict)

    assert virtual_channel.identifier == "Identifier"
    assert virtual_channel.name is None
    assert virtual_channel.desc is None
    assert virtual_channel.attributes == ["AbsDateTime", "DSET", "A"]
    assert virtual_channel.properties is None

    assert virtual_channel.to_dict() == virtual_channel_dict


SETUP_DICT = {
    "attributes": {
        "AbsDateTime": {
            "descr": "Absolutetime in ISO8601, UTC Zone (max. µs)",
            "type": "dateTime",
            "format": "YYYY-MM-DDThh:mm:ss[.ssssss]Z",
        },
        "REFNO": {
            "descr": "Increasing reference number",
            "softLimits": [0, None],
            "diagramScale": "lin",
            "type": "int64",
            "format": "%d",
        },
        "VOLTAGE": {
            "unit": "mV",
            "descr": "Control Voltage",
            "softLimits": [0, 100],
            "diagramScale": "lin",
            "type": "float32",
            "format": "%.2f",
        },
        "TEMP1": {
            "unit": "°C",
            "descr": "Outside temperature",
            "softLimits": [-60, 100],
            "diagramScale": "lin",
            "type": "float32",
            "format": "%.1f",
        },
    },
    "virtual_channels": {
        "0": {
            "name": "Temperature sensor 1",
            "attributes": ["AbsDateTime", "REFNO", "min(TEMP1)", "max(TEMP1)"],
        },
        "1": {
            "name": "Control Signal",
            "descr": "Control signal voltage",
            "attributes": ["AbsDateTime", "REFNO", "VOLTAGE"],
        },
    },
}


def test_setup():
    setup = Setup.from_dict(SETUP_DICT)
    assert len(setup.attributes) == 4
    assert len(setup.virtual_channels) == 2
    assert not setup.is_empty()


def test_setup_empty():
    setup = Setup.from_dict({"attributes": {}, "virtual_channels": {}})
    assert len(setup.attributes) == 0
    assert len(setup.virtual_channels) == 0
    assert setup.is_empty()
