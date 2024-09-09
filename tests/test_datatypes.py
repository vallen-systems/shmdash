from shmdash import Attribute, AttributeType, DiagramScale, VirtualChannel, to_identifier


def test_to_identifier():
    assert to_identifier("id") == "id"
    assert to_identifier("id_123") == "id_123"
    assert to_identifier(123) == "123"
    assert to_identifier("id 1") == "id1"
    assert to_identifier("id(1)") == "id1"
    assert to_identifier("x" * 50) == "x" * 32


def test_attribute():
    attribute_dict = {
        "Identifier": {
            "descr": "Description",
            "unit": "Unit",
            "type": "float32",
            "format": "%.2f",
            "softLimits": (0, None),
            "diagramScale": "lin",
        },
    }

    attributes = list(Attribute.from_dict(attribute_dict))
    attribute = attributes[0]

    assert attribute.identifier == "Identifier"
    assert attribute.desc == "Description"
    assert attribute.unit == "Unit"
    assert attribute.type == AttributeType.FLOAT32
    assert attribute.format == "%.2f"
    assert attribute.soft_limits == (0, None)
    assert attribute.diagram_scale == DiagramScale.LIN

    attribute_dict_parsed = attribute.to_dict()
    assert attribute_dict_parsed == attribute_dict


def test_attribute_minimal():
    attribute_dict = {"Identifier": {"type": "float32"}}

    attributes = list(Attribute.from_dict(attribute_dict))
    attribute = attributes[0]

    assert attribute.identifier == "Identifier"
    assert attribute.desc is None
    assert attribute.unit is None
    assert attribute.type == AttributeType.FLOAT32
    assert attribute.format is None
    assert attribute.soft_limits is None
    assert attribute.diagram_scale is None

    attribute_dict_parsed = attribute.to_dict()
    assert attribute_dict_parsed == attribute_dict


def test_virtual_channel():
    virtual_channel_dict = {
        "Identifier": {
            "name": "Name",
            "descr": "Description",
            "attributes": ["AbsDateTime", "DSET", "A"],
            "prop": ["STREAM", "HIT"],
        },
    }

    virtual_channels = list(VirtualChannel.from_dict(virtual_channel_dict))
    virtual_channel = virtual_channels[0]

    assert virtual_channel.identifier == "Identifier"
    assert virtual_channel.name == "Name"
    assert virtual_channel.desc == "Description"
    assert virtual_channel.attributes == ["AbsDateTime", "DSET", "A"]
    assert virtual_channel.properties == ["STREAM", "HIT"]

    virtual_channel_dict_parsed = virtual_channel.to_dict()
    assert virtual_channel_dict_parsed == virtual_channel_dict


def test_virtual_channel_minimal():
    virtual_channel_dict = {
        "Identifier": {"attributes": ["AbsDateTime", "DSET", "A"]},
    }

    virtual_channels = list(VirtualChannel.from_dict(virtual_channel_dict))
    virtual_channel = virtual_channels[0]

    assert virtual_channel.identifier == "Identifier"
    assert virtual_channel.name is None
    assert virtual_channel.desc is None
    assert virtual_channel.attributes == ["AbsDateTime", "DSET", "A"]
    assert virtual_channel.properties is None

    virtual_channel_dict_parsed = virtual_channel.to_dict()
    assert virtual_channel_dict_parsed == virtual_channel_dict
