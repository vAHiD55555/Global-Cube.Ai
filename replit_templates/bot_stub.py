"""
bot_stub.py
A minimal bot script you can run as an independent Repl instance if you prefer separate Repls for each bot.
This is a simplified version of the mediator's send logic (text only).

Env vars needed:
- MATRIX_HOMESERVER (optional)
- MATRIX_USER
- MATRIX_PASS
- HUGGINGFACE_API_TOKEN
- HF_MODEL (optional)
- SYSTEM_PROMPT (optional)
- ROOM_ID

Run: python bot_stub.py
"""

import os
import asyncio
import aiohttp
from nio import AsyncClient, MatrixRoom, RoomMessageText

HOMESERVER = os.environ.get("MATRIX_HOMESERVER", "https://matrix.org")
MATRIX_USER = os.environ.get("MATRIX_USER")
MATRIX_PASS = os.environ.get("MATRIX_PASS")
ROOM_ID = os.environ.get("ROOM_ID")
HF_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")
HF_MODEL = os.environ.get("HF_MODEL", "bigscience/bloomz-1b1")
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "You are a short creative assistant. Reply concisely in Persian.")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "150"))

if not all([MATRIX_USER, MATRIX_PASS, HF_TOKEN, ROOM_ID]):
    print("Missing ENV vars. See replit_README.md")
    raise SystemExit(1)

async def query_hf_text(prompt: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Accept": "application/json"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False}}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    return data[0].get('generated_text') or str(data[0])
                return str(data)
            else:
                return f"HTTP {resp.status}: {await resp.text()}"

async def main():
    client = AsyncClient(HOMESERVER, MATRIX_USER)
    await client.login(MATRIX_PASS)

    async def message_callback(room: MatrixRoom, event: RoomMessageText):
        if event.sender == MATRIX_USER:
            return
        if ROOM_ID and room.room_id != ROOM_ID:
            return
        body = event.body.strip()
        prompt = f"{SYSTEM_PROMPT}\n\nUser: {body}\nAssistant:"
        resp = await query_hf_text(prompt)
        await client.room_send(room.room_id, "m.room.message", {"msgtype": "m.text", "body": resp})

    client.add_event_callback(message_callback, RoomMessageText)
    print("Bot running and syncing...")
    await client.sync_forever(timeout=30000)

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
