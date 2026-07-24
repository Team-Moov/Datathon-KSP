"""Confirm sample rate by saving decoded audio to WAV and checking duration."""
import asyncio, os, base64, wave, struct, io

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    os.path.dirname(__file__), "..", "secrets", "gcp-service-account.json"
)
from google import genai
from google.genai import types

async def probe():
    client = genai.Client(vertexai=True, project="karnataka-crime-analytics", location="us-central1")
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(role="user", parts=[types.Part(text="You are helpful.")]),
    )
    pcm_chunks = []
    async with client.aio.live.connect(model="gemini-live-2.5-flash-native-audio", config=config) as session:
        await session.send(input="Say: Hello world!", end_of_turn=True)
        async for response in session.receive():
            sc = response.server_content
            if sc and sc.model_turn and sc.model_turn.parts:
                for part in sc.model_turn.parts:
                    if part.inline_data and isinstance(part.inline_data.data, bytes):
                        pcm_chunks.append(base64.b64decode(part.inline_data.data))
            if sc and sc.turn_complete:
                break
    total_pcm = b"".join(pcm_chunks)
    print(f"Total decoded PCM bytes: {len(total_pcm)}")
    for rate in [16000, 22050, 24000, 44100, 48000]:
        dur = len(total_pcm) / (rate * 2)
        print(f"  {rate} Hz mono PCM16 -> {dur:.2f}s")
    # Save as WAV at 24kHz to verify
    wav_path = os.path.join(os.path.dirname(__file__), "test_output_24k.wav")
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(24000)
        wf.writeframes(total_pcm)
    print(f"Saved WAV: {wav_path} (open it to verify quality)")

asyncio.run(probe())
