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


def test_setup():
    setup_dict = {
        "attributes": {
            "AbsDateTime": {
                "descr": "Absolute time UTC",
                "type": "dateTime",
                "format": "YYYY-MM-DDThh:mm:ss.ssssssZ",
            },
            "Pressure": {
                "descr": "Atmospheric pressure",
                "unit": "hPa",
                "type": "float32",
                "format": "%.2f",
                "softLimits": (900, 1100),
            },
        },
        "virtual_channels": {
            "0": {
                "attributes": ["AbsDateTime", "Pressure"],
            },
        },
    }
    setup = Setup.from_dict(setup_dict)
    assert len(setup.attributes) == 2
    assert len(setup.virtual_channels) == 1
    assert not setup.is_empty()


def test_setup_empty():
    setup = Setup.from_dict({"attributes": {}, "virtual_channels": {}})
    assert len(setup.attributes) == 0
    assert len(setup.virtual_channels) == 0
    assert setup.is_empty()
