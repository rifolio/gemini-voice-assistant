from app.tools import FAKE_BOOKINGS, get_trip_info, get_tool_declarations, run_tool


def test_get_trip_info_returns_hardcoded_booking() -> None:
    result = get_trip_info(271234567)

    assert result["found"] is True
    assert result["booking_id"] == 271234567
    assert result["email"] == "alex.jensen@example.com"
    assert result["customer_name"] == "Alex Jensen"
    assert result["destination"] == "Barcelona (BCN)"
    assert result["status"] == "confirmed"


def test_tool_declarations_do_not_leak_real_booking_values() -> None:
    text = str(get_tool_declarations())
    assert "271234567" not in text
    assert "alex.jensen" not in text


def test_get_trip_info_handles_unknown_booking() -> None:
    result = get_trip_info(200000000)

    assert result["found"] is False
    assert result["booking_id"] == 200000000
    assert "No booking found" in result["message"]


def test_get_trip_info_returns_booking_by_email() -> None:
    result = get_trip_info(email="alex.jensen@example.com")

    assert result["found"] is True
    assert result["booking_id"] == 271234567
    assert result["email"] == "alex.jensen@example.com"
    assert result["customer_name"] == "Alex Jensen"


def test_fake_booking_emails_are_unique() -> None:
    emails = [booking["email"] for booking in FAKE_BOOKINGS.values()]

    assert len(emails) == len(set(emails))


def test_get_trip_info_matches_email_case_insensitively() -> None:
    result = get_trip_info(email=" Alex.Jensen@Example.com ")

    assert result["found"] is True
    assert result["booking_id"] == 271234567


def test_get_trip_info_handles_unknown_email() -> None:
    result = get_trip_info(email="missing@example.com")

    assert result["found"] is False
    assert result["email"] == "missing@example.com"
    assert "No booking found" in result["message"]


def test_run_tool_dispatches_known_tool() -> None:
    result = run_tool("get_trip_info", {"booking_id": 271234567})

    assert result["status"] == "confirmed"


def test_run_tool_dispatches_booking_lookup_by_email() -> None:
    result = run_tool("get_trip_info", {"email": "alex.jensen@example.com"})

    assert result["status"] == "confirmed"
    assert result["booking_id"] == 271234567


def test_run_tool_returns_error_for_unknown_tool() -> None:
    result = run_tool("missing_tool", {})

    assert result["status"] == "error"
    assert result["message"] == "Unknown tool: missing_tool"


def test_run_tool_requires_booking_id_or_email() -> None:
    result = run_tool("get_trip_info", {})

    assert result == {"status": "error", "message": "booking_id or email is required"}


def test_run_tool_rejects_none_booking_id_without_email() -> None:
    result = run_tool("get_trip_info", {"booking_id": None})

    assert result == {"status": "error", "message": "booking_id or email is required"}


def test_run_tool_rejects_non_numeric_booking_id() -> None:
    result = run_tool("get_trip_info", {"booking_id": "RIFO-42"})

    assert result == {"status": "error", "message": "booking_id must be a 9-digit number"}


def test_run_tool_rejects_blank_email_without_booking_id() -> None:
    result = run_tool("get_trip_info", {"email": "   "})

    assert result == {"status": "error", "message": "booking_id or email is required"}


def test_tool_declaration_contains_get_trip_info_and_hang_up() -> None:
    declarations = get_tool_declarations()
    names = [d["name"] for d in declarations]

    assert "get_trip_info" in names
    assert "hang_up" in names

    trip_decl = next(d for d in declarations if d["name"] == "get_trip_info")
    assert trip_decl["parameters"]["properties"]["booking_id"]["type"] == "integer"
    assert trip_decl["parameters"]["properties"]["email"]["type"] == "string"
    assert trip_decl["parameters"]["required"] == []
