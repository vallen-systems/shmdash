from shmdash import to_identifier


def test_to_identifier():
    assert to_identifier("id") == "id"
    assert to_identifier("id_123") == "id_123"
    assert to_identifier(123) == "123"
    assert to_identifier("id 1") == "id1"
    assert to_identifier("id(1)") == "id1"
    assert to_identifier("x" * 50) == "x" * 32
