import pytest
from pydantic import ValidationError

from app.schemas import (
    AudioChunkEvent,
    ClientEvent,
    ErrorEvent,
    SessionStatusEvent,
    ToolCallEvent,
    ToolResultEvent,
    TranscriptEvent,
)


def test_client_start_session_event() -> None:
    event = ClientEvent.model_validate(
        {"type": "start_session", "system_prompt": "Be concise."}
    )

    assert event.type == "start_session"
    assert event.system_prompt == "Be concise."


def test_client_user_text_event_requires_text() -> None:
    with pytest.raises(ValidationError):
        ClientEvent.model_validate({"type": "user_text"})


def test_transcript_event_serializes_role_and_text() -> None:
    event = TranscriptEvent(role="assistant", text="Hello")

    assert event.model_dump() == {
        "type": "transcript",
        "role": "assistant",
        "text": "Hello",
    }


def test_tool_events_include_ids() -> None:
    call = ToolCallEvent(id="call-1", name="get_trip_info", args={"booking_code": "RIFO-42"})
    result = ToolResultEvent(id="call-1", status="ok", result={"status": "confirmed"})

    assert call.type == "tool_call"
    assert result.type == "tool_result"
    assert call.model_dump()["id"] == "call-1"
    assert result.model_dump()["id"] == "call-1"


def test_audio_chunk_event_serializes_defaults() -> None:
    assert AudioChunkEvent(data_base64="AA==").model_dump() == {
        "type": "audio_chunk",
        "format": "pcm_s16le",
        "sample_rate": 24000,
        "data_base64": "AA==",
    }


def test_status_and_error_events() -> None:
    assert SessionStatusEvent(status="connected").model_dump() == {
        "type": "session_status",
        "status": "connected",
    }
    assert ErrorEvent(message="Missing key").model_dump() == {
        "type": "error",
        "message": "Missing key",
    }
