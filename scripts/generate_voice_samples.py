#!/usr/bin/env python3
"""Generate a WAV voice-sample file for each Gemini prebuilt voice.

Run from the project root:
    .venv/bin/python scripts/generate_voice_samples.py

Output: static/voices/<voice>.wav  (one file per voice)
"""

import os
import struct
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

VOICES = ["Aoede", "Charon", "Fenrir", "Kore", "Leda", "Orus", "Puck", "Zephyr"]
SAMPLE_TEXT = (
    "Hello, this is Rifo Traveling customer support. How can I help you today?"
)
TTS_MODEL = "gemini-2.5-flash-preview-tts"
OUTPUT_DIR = Path(__file__).parent.parent / "static" / "voices"
SAMPLE_RATE = 24000


def pcm_to_wav(pcm: bytes, rate: int = SAMPLE_RATE, channels: int = 1, bits: int = 16) -> bytes:
    data_size = len(pcm)
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, channels, rate,
        rate * channels * bits // 8,
        channels * bits // 8, bits,
        b"data", data_size,
    ) + pcm


def generate(client: object, voice: str) -> bytes:
    from google.genai import types  # type: ignore[import]

    resp = client.models.generate_content(  # type: ignore[attr-defined]
        model=TTS_MODEL,
        contents=SAMPLE_TEXT,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    return resp.candidates[0].content.parts[0].inline_data.data


def main() -> None:
    from google import genai  # type: ignore[import]

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for voice in VOICES:
        out = OUTPUT_DIR / f"{voice.lower()}.wav"
        print(f"  {voice:<10}", end=" ", flush=True)
        try:
            pcm = generate(client, voice)
            out.write_bytes(pcm_to_wav(pcm))
            print(f"→ {out.name}  ({len(pcm):,} bytes PCM)")
        except Exception as exc:
            print(f"FAILED: {exc}")

    print("Done.")


if __name__ == "__main__":
    main()
