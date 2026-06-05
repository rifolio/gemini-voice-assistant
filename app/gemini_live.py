import asyncio
import base64
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from app.schemas import (
    AudioChunkEvent,
    ErrorEvent,
    HangUpEvent,
    ToolCallEvent,
    ToolResultEvent,
    TranscriptEvent,
)
from app.tools import HANG_UP, get_tool_declarations, run_tool

DEFAULT_VOICE = "Aoede"


def build_live_config(system_prompt: str, voice: str = DEFAULT_VOICE) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system_prompt,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        tools=[{"function_declarations": get_tool_declarations()}],
    )


class GeminiLiveBridge:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self._session: Any = None
        self._cm: Any = None
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def open(self, system_prompt: str, voice: str = DEFAULT_VOICE) -> None:
        config = build_live_config(system_prompt, voice)
        self._cm = self.client.aio.live.connect(model=self.model, config=config)
        self._session = await self._cm.__aenter__()

    async def close(self) -> None:
        await self._audio_queue.put(None)  # unblock _send_loop
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._cm = None
            self._session = None

    async def send_text(self, text: str) -> None:
        await self._session.send_realtime_input(text=text)

    async def send_audio(self, data: bytes) -> None:
        await self._audio_queue.put(data)

    async def _incoming_audio(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                break
            yield chunk

    async def _send_loop(self) -> None:
        mime_type = "audio/pcm;rate=16000"
        async for chunk in self._incoming_audio():
            await self._session.send_realtime_input(
                audio=types.Blob(data=chunk, mime_type=mime_type)
            )

    async def receive_events(
        self,
    ) -> AsyncIterator[AudioChunkEvent | ErrorEvent | HangUpEvent | ToolCallEvent | ToolResultEvent | TranscriptEvent]:
        sender_task = asyncio.create_task(self._send_loop())
        try:
            while not sender_task.done():
                async for response in self._session.receive():
                    async for event in self._process_response(response):
                        yield event
                        if isinstance(event, HangUpEvent):
                            return
                # SDK receive iterator exits at turn boundaries; loop back to keep
                # the same Live session alive for the next user turn.
                await asyncio.sleep(0)
        finally:
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass

    async def _process_response(
        self, response: Any
    ) -> AsyncIterator[AudioChunkEvent | HangUpEvent | ToolCallEvent | ToolResultEvent | TranscriptEvent]:
        server_content = getattr(response, "server_content", None)
        if server_content is not None:
            model_turn = getattr(server_content, "model_turn", None)
            parts = getattr(model_turn, "parts", []) if model_turn is not None else []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is not None and getattr(inline_data, "data", None):
                    yield self.audio_event_from_bytes(inline_data.data)
                text = getattr(part, "text", None)
                if text:
                    yield TranscriptEvent(role="assistant", text=text)

            output_transcription = getattr(server_content, "output_transcription", None)
            if output_transcription is not None:
                text = getattr(output_transcription, "text", None)
                if text:
                    yield TranscriptEvent(role="assistant", text=text)

            input_transcription = getattr(server_content, "input_transcription", None)
            if input_transcription is not None:
                text = getattr(input_transcription, "text", None)
                if text:
                    yield TranscriptEvent(role="user", text=text)

        tool_call = getattr(response, "tool_call", None)
        function_calls = getattr(tool_call, "function_calls", []) if tool_call is not None else []
        if function_calls:
            hang_up_called = False
            tool_responses = []
            for index, fc in enumerate(function_calls):
                call_id = getattr(fc, "id", None) or f"tool-{index}"
                name = getattr(fc, "name", "")
                args = dict(getattr(fc, "args", {}) or {})
                events = await self.handle_tool_call(call_id=call_id, name=name, args=args)
                for event in events:
                    yield event
                tool_responses.append(
                    types.FunctionResponse(
                        id=call_id,
                        name=name,
                        response=events[-1].result,
                    )
                )
                if name == HANG_UP:
                    hang_up_called = True

            await self._session.send_tool_response(function_responses=tool_responses)

            if hang_up_called:
                await self._audio_queue.put(None)  # stop sender loop
                yield HangUpEvent()

    async def handle_tool_call(
        self,
        call_id: str,
        name: str,
        args: dict[str, Any],
    ) -> list[ToolCallEvent | ToolResultEvent]:
        call_event = ToolCallEvent(id=call_id, name=name, args=args)
        result = run_tool(name, args)
        status = "error" if result.get("status") == "error" else "ok"
        result_event = ToolResultEvent(id=call_id, status=status, result=result)
        return [call_event, result_event]

    @staticmethod
    def audio_event_from_bytes(data: bytes) -> AudioChunkEvent:
        return AudioChunkEvent(data_base64=base64.b64encode(data).decode("ascii"))
