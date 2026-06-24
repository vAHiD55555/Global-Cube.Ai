Replit quickstart for dev/mediator

Steps (mobile-friendly):
1. Open https://replit.com and sign in.
2. Create a new Repl: choose "Python".
3. In Files, create a folder named `replit_templates` and copy files from this repo into it, OR fork this repo in Replit directly.
4. In Secrets (Environment variables) add the following values:
   - MEDIATOR_USER, MEDIATOR_PASS
   - BOT_A_USER, BOT_A_PASS
   - BOT_B_USER, BOT_B_PASS
   - ROOM_ID (matrix room id, e.g. !abcdef:matrix.org)
   - HUGGINGFACE_API_TOKEN
   - HF_MODEL (e.g. bigscience/bloomz-1b1)
   - TTS_MODEL (optional, for audio)
   - SYSTEM_PROMPT_A and SYSTEM_PROMPT_B (optional)
5. Install requirements: use the Replit package tool or run `pip install -r replit_templates/requirements.txt` in the console.
6. Run: `python replit_templates/mediator.py`

Testing:
- Open Element and send a message in the ROOM_ID. The mediator account will listen and one of the bot accounts (A or B) will reply.
- Check Replit console for logs and any HF errors.

Notes:
- Keep your HF token private (use Replit Secrets).
- This is a minimal dev setup for testing. After testing we can harden, add retries, rate-limiting, and richer TTS/ASR flows.
