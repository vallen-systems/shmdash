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
        "AbsDateTime": {
            "descr": "Absolutetime in ISO8601, UTC Zone (max. μs)",
            "unit": None,
            "type": "dateTime",
            "format": "YYYY-MM-DDThh:mm:ss[.ssssss]Z",
            "softLimits": (0, None),
            "diagramScale": "lin",
        },
    }

    attributes = list(Attribute.from_dict(attribute_dict))
    attribute = attributes[0]

    assert attribute.identifier == "AbsDateTime"
    assert attribute.desc == "Absolutetime in ISO8601, UTC Zone (max. μs)"
    assert attribute.unit is None
    assert attribute.type == AttributeType.DATETIME
    assert attribute.format == "YYYY-MM-DDThh:mm:ss[.ssssss]Z"
    assert attribute.soft_limits == (0, None)
    assert attribute.diagram_scale == DiagramScale.LIN

    attribute_dict_parsed = attribute.to_dict()
    assert attribute_dict_parsed == attribute_dict


def test_virtual_channel():
    virtual_channel_dict = {
        "100": {
            "name": "Name",
            "descr": "Description",
            "attributes": ["AbsDateTime", "DSET", "A"],
            "prop": ["STREAM", "HIT"],
        },
    }

    virtual_channels = list(VirtualChannel.from_dict(virtual_channel_dict))
    virtual_channel = virtual_channels[0]

    assert virtual_channel.identifier == "100"
    assert virtual_channel.name == "Name"
    assert virtual_channel.desc == "Description"
    assert virtual_channel.attributes == ["AbsDateTime", "DSET", "A"]
    assert virtual_channel.properties == ["STREAM", "HIT"]

    virtual_channel_dict_parsed = virtual_channel.to_dict()
    assert virtual_channel_dict_parsed == virtual_channel_dict
