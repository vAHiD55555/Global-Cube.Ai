"""
mediator.py
Mediator for Matrix bots: listens as MEDIATOR account, chooses BOT_A or BOT_B to respond (round-robin), calls Hugging Face for text generation and (optionally) TTS, then posts reply as the chosen bot.

Environment variables (set these in Replit Secrets or .env):
- MATRIX_HOMESERVER (optional, default: https://matrix.org)
- MEDIATOR_USER, MEDIATOR_PASS
- BOT_A_USER, BOT_A_PASS
- BOT_B_USER, BOT_B_PASS
- ROOM_ID (the Matrix room id to monitor)
- HUGGINGFACE_API_TOKEN
- HF_MODEL (text gen model, default: bigscience/bloomz-1b1)
- TTS_MODEL (optional; if set, mediator will request audio from HF and upload)
- MAX_NEW_TOKENS (optional, default: 150)

Run: python mediator.py
"""

import os
import asyncio
import aiohttp
import tempfile
from nio import AsyncClient, MatrixRoom, RoomMessageText

HOMESERVER = os.environ.get("MATRIX_HOMESERVER", "https://matrix.org")
MEDIATOR_USER = os.environ.get("MEDIATOR_USER")
MEDIATOR_PASS = os.environ.get("MEDIATOR_PASS")
BOT_A_USER = os.environ.get("BOT_A_USER")
BOT_A_PASS = os.environ.get("BOT_A_PASS")
BOT_B_USER = os.environ.get("BOT_B_USER")
BOT_B_PASS = os.environ.get("BOT_B_PASS")
ROOM_ID = os.environ.get("ROOM_ID")
HF_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")
HF_MODEL = os.environ.get("HF_MODEL", "bigscience/bloomz-1b1")
TTS_MODEL = os.environ.get("TTS_MODEL")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "150"))

if not all([MEDIATOR_USER, MEDIATOR_PASS, BOT_A_USER, BOT_A_PASS, BOT_B_USER, BOT_B_PASS, HF_TOKEN, ROOM_ID]):
    print("Error: Missing one or more required environment variables. See replit_README.md for setup.")
    raise SystemExit(1)

# simple round-robin counter
counter = 0

async def query_hf_text(prompt: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Accept": "application/json"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False}}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, dict) and "error" in data:
                    return "[HF Error] " + data.get("error")
                if isinstance(data, list):
                    text = data[0].get("generated_text") or data[0].get("summary_text") or str(data[0])
                    return text
                return str(data)
            else:
                text = await resp.text()
                return f"HTTP {resp.status}: {text}"

async def query_hf_tts(text: str) -> bytes:
    # If TTS_MODEL is set, request audio/wav from HF Inference
    if not TTS_MODEL:
        return b""
    url = f"https://api-inference.huggingface.co/models/{TTS_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Accept": "audio/wav"}
    payload = {"inputs": text}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
            if resp.status == 200:
                data = await resp.read()
                return data
            else:
                print("TTS HTTP", resp.status)
                return b""

async def upload_and_send_audio(client: AsyncClient, room_id: str, audio_bytes: bytes, filename: str = "resp.wav"):
    if not audio_bytes:
        return
    # matrix-nio upload
    m = await client.upload(content=audio_bytes, content_type="audio/wav", filename=filename)
    content_uri = m  # upload returns content URI or dict depending on version
    # Some versions return dict: {'content_uri': 'mxc://...'}
    if isinstance(m, dict) and m.get('content_uri'):
        content_uri = m['content_uri']
    info = {"mimetype": "audio/wav", "size": len(audio_bytes)}
    await client.room_send(
        room_id,
        message_type="m.room.message",
        content={
            "msgtype": "m.audio",
            "body": filename,
            "url": content_uri,
            "info": info
        }
    )

async def main():
    global counter
    mediator = AsyncClient(HOMESERVER, MEDIATOR_USER)
    bot_a = AsyncClient(HOMESERVER, BOT_A_USER)
    bot_b = AsyncClient(HOMESERVER, BOT_B_USER)

    await mediator.login(MEDIATOR_PASS)
    await bot_a.login(BOT_A_PASS)
    await bot_b.login(BOT_B_PASS)

    print("Mediator and bot clients logged in. Listening...")

    async def message_callback(room: MatrixRoom, event: RoomMessageText):
        global counter
        try:
            sender = event.sender
            body = event.body.strip()
        except Exception:
            return
        # ignore messages from our own accounts
        if sender in [MEDIATOR_USER, BOT_A_USER, BOT_B_USER]:
            return
        # only react in target ROOM_ID
        if ROOM_ID and room.room_id != ROOM_ID:
            return

        # choose bot by round-robin
        chosen = 'A' if counter % 2 == 0 else 'B'
        counter += 1

        if chosen == 'A':
            bot_client = bot_a
            system_prompt = os.environ.get('SYSTEM_PROMPT_A', 'You are Aurora, a short creative collaborator. Answer concisely in Persian.')
        else:
            bot_client = bot_b
            system_prompt = os.environ.get('SYSTEM_PROMPT_B', 'You are Atlas, a constructive critic. Keep answers brief and polite in Persian.')

        prompt = f"{system_prompt}\n\nUser: {body}\nAssistant:"
        await mediator.room_typing(room.room_id, timeout=1000)
        text_resp = await query_hf_text(prompt)

        # send text as the chosen bot
        await bot_client.room_send(
            room.room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": text_resp}
        )

        # optional: TTS
        if TTS_MODEL:
            audio = await query_hf_tts(text_resp)
            if audio:
                await upload_and_send_audio(bot_client, room.room_id, audio)

    mediator.add_event_callback(message_callback, RoomMessageText)

    # sync forever (mediator client does the listening)
    await mediator.sync_forever(timeout=30000)

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
