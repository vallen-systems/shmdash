from shmdash import ResponseError


def test_response_error():
    error = ResponseError("URL", method="POST", status=403)
    assert error.url == "URL"
    assert error.method == "POST"
    assert error.status == 403
    assert str(error) == "POST request to URL failed with status 403 (Forbidden)"


def test_response_error_with_message():
    error = ResponseError("URL", method="POST", status=403, message="message")
    assert str(error) == "POST request to URL failed with status 403 (Forbidden): message"
