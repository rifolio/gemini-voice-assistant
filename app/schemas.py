from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ClientEvent(BaseModel):
    type: Literal["start_session", "user_text", "stop_session", "user_audio"]
    system_prompt: str | None = None
    voice: str | None = None
    text: str | None = None
    data_base64: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "ClientEvent":
        if self.type == "start_session" and not self.system_prompt:
            raise ValueError("system_prompt is required for start_session")
        if self.type == "user_text" and not self.text:
            raise ValueError("text is required for user_text")
        return self


class SessionStatusEvent(BaseModel):
    type: Literal["session_status"] = "session_status"
    status: str


class TranscriptEvent(BaseModel):
    type: Literal["transcript"] = "transcript"
    role: Literal["user", "assistant"]
    text: str


class AudioChunkEvent(BaseModel):
    type: Literal["audio_chunk"] = "audio_chunk"
    format: Literal["pcm_s16le"] = "pcm_s16le"
    sample_rate: int = 24000
    data_base64: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    id: str
    status: Literal["ok", "error"]
    result: dict[str, Any]


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class HangUpEvent(BaseModel):
    type: Literal["hang_up"] = "hang_up"
    message: str = "The agent has ended the call."
