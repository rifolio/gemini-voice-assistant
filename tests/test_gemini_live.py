import base64

import pytest

from app.gemini_live import GeminiLiveBridge, build_live_config
from app.schemas import AudioChunkEvent, ToolCallEvent, ToolResultEvent


def test_build_live_config_uses_prompt_and_tool() -> None:
    config = build_live_config("Be helpful.")

    assert config.response_modalities == ["AUDIO"]
    assert config.system_instruction == "Be helpful."
    assert config.tools[0].function_declarations[0].name == "get_trip_info"
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Aoede"
    assert config.output_audio_transcription is not None
    assert config.input_audio_transcription is not None


def test_audio_event_encodes_pcm_bytes() -> None:
    event = GeminiLiveBridge.audio_event_from_bytes(b"\x00\x01")

    assert isinstance(event, AudioChunkEvent)
    assert event.data_base64 == base64.b64encode(b"\x00\x01").decode("ascii")


@pytest.mark.asyncio
async def test_handle_tool_call_emits_call_and_result() -> None:
    bridge = GeminiLiveBridge(api_key="test-key", model="gemini-3.1-flash-live-preview")

    events = await bridge.handle_tool_call(
        call_id="call-1",
        name="get_trip_info",
        args={"booking_id": 271234567},
    )

    assert isinstance(events[0], ToolCallEvent)
    assert isinstance(events[1], ToolResultEvent)
    assert events[0].name == "get_trip_info"
    assert events[1].status == "ok"
    assert events[1].result["status"] == "confirmed"


@pytest.mark.asyncio
async def test_handle_unknown_tool_emits_error_result() -> None:
    bridge = GeminiLiveBridge(api_key="test-key", model="gemini-3.1-flash-live-preview")

    events = await bridge.handle_tool_call(call_id="call-2", name="missing_tool", args={})

    assert events[1].status == "error"
    assert events[1].result["message"] == "Unknown tool: missing_tool"
