from typing import Any


GET_TRIP_INFO = "get_trip_info"
HANG_UP = "hang_up"

FAKE_BOOKINGS: dict[int, dict[str, Any]] = {
    271234567: {
        "email": "alex.jensen@example.com",
        "customer_name": "Alex Jensen",
        "origin": "Copenhagen (CPH)",
        "destination": "Barcelona (BCN)",
        "airline": "Rifo Traveling",
        "flight_number": "RF 201",
        "departure": "2026-06-12T07:45",
        "arrival": "2026-06-12T10:20",
        "hotel": "Rifo Barcelona Central",
        "check_in": "2026-06-12",
        "check_out": "2026-06-15",
        "status": "confirmed",
        "support_note": "Customer requested early check-in if available.",
    },
    279876543: {
        "email": "maria.larsen@example.com",
        "customer_name": "Maria Larsen",
        "origin": "Oslo (OSL)",
        "destination": "Rome (FCO)",
        "airline": "Rifo Traveling",
        "flight_number": "RF 314",
        "departure": "2026-07-04T09:15",
        "arrival": "2026-07-04T13:05",
        "hotel": "Rifo Roma Centro",
        "check_in": "2026-07-04",
        "check_out": "2026-07-11",
        "status": "confirmed",
        "support_note": "Vegetarian meal preference on file.",
    },
    274445555: {
        "email": "jonas.petersen@example.com",
        "customer_name": "Jonas Petersen",
        "origin": "Stockholm (ARN)",
        "destination": "Lisbon (LIS)",
        "airline": "Rifo Traveling",
        "flight_number": "RF 522",
        "departure": "2026-08-20T14:30",
        "arrival": "2026-08-20T17:55",
        "hotel": "Rifo Lisboa Oriente",
        "check_in": "2026-08-20",
        "check_out": "2026-08-27",
        "status": "pending_payment",
        "support_note": "Balance due by 2026-07-20.",
    },
    278887001: {
        "email": "amalie.sorensen@example.com",
        "customer_name": "Amalie Sørensen",
        "origin": "Copenhagen (CPH)",
        "destination": "Amsterdam (AMS)",
        "airline": "Rifo Traveling",
        "flight_number": "RF 103",
        "departure": "2026-09-10T06:00",
        "arrival": "2026-09-10T07:50",
        "hotel": "Rifo Amsterdam Centre",
        "check_in": "2026-09-10",
        "check_out": "2026-09-14",
        "status": "cancelled",
        "support_note": "Cancelled by customer. Refund processed.",
    },
}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _find_booking_by_email(email: str) -> tuple[int, dict[str, Any]] | None:
    normalized_email = _normalize_email(email)
    for booking_id, booking in FAKE_BOOKINGS.items():
        if _normalize_email(str(booking["email"])) == normalized_email:
            return booking_id, booking
    return None


def get_trip_info(booking_id: int | None = None, email: str | None = None) -> dict[str, Any]:
    normalized_email = _normalize_email(email) if email is not None else None

    if booking_id is not None:
        booking = FAKE_BOOKINGS.get(booking_id)
        if booking is None:
            return {
                "found": False,
                "booking_id": booking_id,
                "message": "No booking found for that ID.",
            }
        return {"found": True, "booking_id": booking_id, **booking}

    if normalized_email:
        match = _find_booking_by_email(normalized_email)
        if match is None:
            return {
                "found": False,
                "email": normalized_email,
                "message": "No booking found for that email.",
            }
        found_booking_id, booking = match
        return {"found": True, "booking_id": found_booking_id, **booking}

    return {
        "found": False,
        "message": "No booking found because no booking ID or email was provided.",
    }


def _has_lookup_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == HANG_UP:
        return {"status": "ok", "message": "Call ended by agent."}

    if name == GET_TRIP_INFO:
        raw_booking_id = args.get("booking_id")
        raw_email = args.get("email")
        has_booking_id = _has_lookup_value(raw_booking_id)
        has_email = _has_lookup_value(raw_email)

        if not has_booking_id and not has_email:
            return {"status": "error", "message": "booking_id or email is required"}

        if has_booking_id:
            try:
                parsed_booking_id = int(str(raw_booking_id).strip())
            except ValueError:
                return {"status": "error", "message": "booking_id must be a 9-digit number"}
            return get_trip_info(booking_id=parsed_booking_id)

        return get_trip_info(email=str(raw_email))

    return {"status": "error", "message": f"Unknown tool: {name}"}


def get_tool_declarations() -> list[dict[str, Any]]:
    return [
        {
            "name": GET_TRIP_INFO,
            "description": (
                "Look up Rifo Traveling travel booking details by either a 9-digit numeric "
                "booking ID or the customer's unique email address. Returns flight, "
                "hotel, and status information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "integer",
                        "description": "A 9-digit booking ID that starts with 27 (for example, 27 followed by seven more digits).",
                    },
                    "email": {
                        "type": "string",
                        "description": "The customer's unique booking email address (for example, name@example.com).",
                    }
                },
                "required": [],
            },
        },
        {
            "name": HANG_UP,
            "description": (
                "End the phone call and hang up. Use this when the conversation is "
                "complete or when you want to terminate the call."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    ]
