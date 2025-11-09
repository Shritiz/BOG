"""
Multi-bot Main.py
Converted from single-bot architecture to a hybrid multi-bot system.
Features:
- ACTIVE_BOTS list to choose active character modules from settings/characters/*.py
- Dynamic loading of character modules
- Each bot has its own Gemini chat session and own history file
- Shared conversation buffer used to provide context to each bot
- Mention-detection: if user mentions a bot by name it replies first; otherwise a round-robin least-recently-spoken order
- After one bot replies, the shared context is updated and other bots may respond in turn
- Sequential TTS playback (no overlapping)

Drop this file into your BOT/ folder. Keep your existing `settings/` folder and `dependancy/input_audio.py`.
"""

import importlib
import json
import os
import asyncio
import re as regex
import shutil
import unicodedata
import tempfile
import base64
import subprocess
from datetime import datetime
import edge_tts
from datetime import datetime, timezone

import google.generativeai as genai
from settings.settings import Stream_TTS_Setting as STREAM_TTS
from settings.settings import VOICE_SETTING
from dependancy.input_audio import load_model, get_voice_input

# Reuse preprocess_text from original file (trimmed/kept identical behavior)
SYMBOLS = {"∆": "delta ", "±": "plus or minus ", "°": " degrees ", "µ": "micro ", "Ω": "ohm "}
PRONUNCIATION_FIXES = {"NaCl": "sodium chloride", "H2O": "water", "CO2": "carbon dioxide","H2": "hydrogen","ΔH": "delta H","μm": "micrometer",}

def preprocess_text(raw: str) -> str:
    if not raw or not raw.strip():
        return ""
    text = unicodedata.normalize("NFKC", raw)
    for symbol, word in SYMBOLS.items():
        text = text.replace(symbol, word)
    for k, v in PRONUNCIATION_FIXES.items():
        text = text.replace(k, v)
    text = regex.sub(r"(\w)-(\w)", r"\1  \2", text)
    text = regex.sub(r"(\d)\s*-\s*(\d)", r"\1 minus \2", text)
    text = regex.sub(r"(\d)\.(\d)", r"\1 point \2", text)
    text = regex.sub(r"(\d+)-(\d+)", r"\1 to \2", text)
    text = regex.sub(r"(\d+)%", r"\1 percent", text)
    text = regex.sub(r"(\d+)\s*-\s*(\d+)", r"\1 to \2", text)
    text = regex.sub(r"(\d+)\s*%", r"\1 percent", text)
    text = regex.sub(r"(\d+)(st|nd|rd|th)\b", r"\1 \2", text)
    text = regex.sub(r"\$(\d+)", r"\1 dollars", text)
    text = regex.sub(r"(\d+)\s*\$", r"\1 dollars", text)
    text = regex.sub(r"(\d+):(\d+)", r"\1 ratio \2", text)
    text = regex.sub(r"(\d+)\s*:\s*(\d+)", r"\1 ratio \2", text)
    text = regex.sub(r"(\d+)-(\d+)-(\d+)", r"\1 dash \2 dash \3", text)
    text = regex.sub(r"\r|\n", " ", text)
    text = regex.sub(r"\s+", " ", text)
    text = regex.sub(r"([.,;!?])", r"\1 ", text)
    return text.strip()

# === Audio/TTS system (kept from original implementation but wrapped for reuse) ===
async def stream_tts(text: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)

    q = asyncio.Queue()
    async def producer():
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                data = chunk.get("data")
                if isinstance(data, str):
                    try:
                        data = base64.b64decode(data)
                    except Exception:
                        data = data.encode("utf-8")
                await q.put(data)
        await q.put(None)

    prod_task = asyncio.create_task(producer())

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_path = tmp.name
    tmp.close()

    START_BUFFER = 64 * 1024
    player = None
    try:
        buffered = 0
        with open(tmp_path, "ab") as f:
            while True:
                data = await q.get()
                if data is None:
                    break
                f.write(data)
                f.flush()
                buffered += len(data)

                if player is None and buffered >= START_BUFFER:
                    player = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

        await prod_task

        if player:
            player.wait()
        else:
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

async def speak_text(text: str, voice: str):
    # Use STREAM_TTS setting from settings.settings
    if STREAM_TTS:
        await stream_tts(text, voice)
    else:
        tts = edge_tts.Communicate(text, voice)
        out = f"tts_{int(datetime.now(timezone.utc).timestamp())}.mp3"
        await tts.save(out)
        # playsound is blocking — keep sequential play
        from playsound import playsound
        playsound(out)
        try:
            os.remove(out)
        except Exception:
            pass

# === Disk/memory setup ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
MEMORY_DIR = os.path.join(DOCUMENTS_DIR, "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

# Initialize Vosk (voice input) using same logic as original
VOSK_MODEL_PATH = os.path.join(BASE_DIR, "vosk-model-small-en-us-0.15")
if not os.path.exists(VOSK_MODEL_PATH):
    alt = os.path.join(os.getcwd(), "vosk-model-small-en-us-0.15")
    if os.path.exists(alt):
        VOSK_MODEL_PATH = alt
    else:
        print(f"⚠️ Vosk model not found at {VOSK_MODEL_PATH} or {alt}")

load_model(VOSK_MODEL_PATH)

# === Active bots configuration ===
# You can also move ACTIVE_BOTS into settings.settings if you prefer.
ACTIVE_BOTS = ["Sofi", "Lumi", "Martin"]  # default — change as needed
CHARACTERS_DIR = os.path.join(BASE_DIR, "settings", "characters")

# === Helper: dynamic character loader ===
def load_character_module(name: str):
    # Attempt to import settings.characters.<lowername>
    module_name = f"settings.characters.{name.lower()}"
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        # Fallback: try capitalized
        module_name = f"settings.characters.{name}"
        try:
            mod = importlib.import_module(module_name)
        except Exception as e:
            raise ImportError(f"Could not import character module for '{name}': {e}")
    # Validate required attributes
    required = ["CHARACTER_NAME", "CHARACTER_DESCRIPTION", "MODEL_NAME"]
    for r in required:
        if not hasattr(mod, r):
            raise AttributeError(f"Character module {module_name} missing required attr {r}")
    return mod

# === BotSession class ===
class BotSession:
    def __init__(self, char_module):
        # character module is the imported python module
        self.module = char_module
        self.name = getattr(char_module, "CHARACTER_NAME")
        self.description = getattr(char_module, "CHARACTER_DESCRIPTION")
        self.model_name = getattr(char_module, "MODEL_NAME")
        self.voice = getattr(char_module, "MODEL_VOICE", "en-US-GuyNeural")

        # history file path per character
        safe_name = self.name.lower().replace(" ", "_")
        self.history_file = os.path.join(MEMORY_DIR, f"{safe_name}_history.json")

        # load history
        self.history = self._load_history()

        # Instantiate the generative model for this character
        # We include the character description as the system instruction
        self.model = genai.GenerativeModel(
            self.model_name,
            system_instruction=self.description,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        )
        self.chat = self.model.start_chat(history=self.history)
        # timestamp of last speak — used for turn order
        self.last_spoke = None

    def _load_history(self):
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [{"role": msg.get("role", "user"), "parts": [{"text": msg.get("content", "")}]} for msg in data]
        except Exception:
            return []

    def save_history(self):
        try:
            serializable = []
            for msg in self.chat.history:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                else:
                    role = getattr(msg, "role", "unknown")
                    content = " ".join([part.text for part in getattr(msg, "parts", []) if hasattr(part, "text")])
                serializable.append({"role": role, "content": content})
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Failed to save history for {self.name}: {e}")

    def send_user_message(self, message: str):
        # Add a user message to this bot's chat
        return self.chat.send_message(message)

    def send_assistant_message(self, message: str):
        # Add assistant message (bot's own reply) into its chat
        return self.chat.send_message(message)

    def generate_response(self, prompt: str):
        # Blocking call to the model to generate; returns the response object
        return self.chat.send_message(prompt)

# === Shared conversation buffer ===
shared_conversation = []  # list of dicts: {"speaker": "User"/bot, "text": "...", "time": "..."}

# windowing for context sent to models
CONTEXT_WINDOW = 20  # number of recent utterances to include

# initialize gemini API key if present in env
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# === Load all active bots ===
bots = {}
for bot_name in ACTIVE_BOTS:
    try:
        mod = load_character_module(bot_name)
        bots[mod.CHARACTER_NAME] = BotSession(mod)
    except Exception as e:
        print(f"⚠️ Skipping bot '{bot_name}': {e}")

if not bots:
    raise RuntimeError("No active bots loaded. Check ACTIVE_BOTS and settings/characters/ modules.")

# helper: mention detection
def detect_mentioned_bot(user_text: str):
    # simple regex to find exact bot names (case-insensitive)
    for name in bots.keys():
        pattern = r"\b" + regex.escape(name) + r"\b"
        if regex.search(pattern, user_text, flags=regex.IGNORECASE):
            return name
    return None

# helper: pick next bot when no mention is present (least recently spoken)
def pick_next_bot():
    # sort bots by last_spoke (None first) so idle bots speak first
    ordered = sorted(bots.values(), key=lambda b: (b.last_spoke is not None, b.last_spoke or datetime.fromtimestamp(0)))
    return ordered[0]

# helper: build context string from shared_conversation
def build_context_for_bot(max_utts=CONTEXT_WINDOW):
    recent = shared_conversation[-max_utts:]
    parts = []
    for item in recent:
        speaker = item.get("speaker", "Unknown")
        text = item.get("text", "")
        parts.append(f"{speaker}: {text}")
    return "\n".join(parts)

# helper: print with simple delim
columns = shutil.get_terminal_size().columns

def print_bot(speaker, text):
    print("=" * columns)
    print(f"{speaker}: {text}\n")

# main run loop
async def main_loop():
    print(f"🤖 Multi-bot chat ready! Active: {', '.join(bots.keys())}")
    print("Type 'exit' or 'quit' to stop.\n")

    voice = VOICE_SETTING
    round_index = 0

    while True:
        try:
            print("=" * columns)
            if voice:
                user_input = get_voice_input("🎙️ Press Alt+P to record...")
                print(f"You: {user_input}\n")
            else:
                user_input = input("You: ").strip()

            if not user_input:
                print("⚠️ No input detected. Please try again.")
                continue
            if user_input.lower() in {"exit", "quit"}:
                print("Chat ended. Bye!")
                break

            # preprocess
            p_user = preprocess_text(user_input)
            # append to shared conversation
            shared_conversation.append({"speaker": "You", "text": p_user, "time": datetime.now(timezone.utc).isoformat()})

            # determine who goes first
            mentioned = detect_mentioned_bot(user_input)
            if mentioned:
                first_bot = bots.get(mentioned)
            else:
                first_bot = pick_next_bot()
            context = build_context_for_bot()
            prompt = (
                f"You are {first_bot.name}. Respond naturally based on the conversation below. "
                f"Refer to other participants by name when appropriate. Be concise but natural.\n\n{context}\n\n"
                f"{first_bot.name}, your response:"
            )

            try:
                resp = first_bot.generate_response(prompt)
                bot_text = regex.sub(r"[\\*/]+", "", resp.text)
                bot_text = preprocess_text(bot_text)

                shared_conversation.append({
                    "speaker": first_bot.name,
                    "text": bot_text,
                    "time": datetime.now(timezone.utc).isoformat(),
                })
                first_bot.last_spoke = datetime.now(timezone.utc)
                print_bot(first_bot.name, bot_text)
                await speak_text(bot_text, first_bot.voice)
                first_bot.save_history()


            except Exception as e:
                print(f"⚠️ Error generating response for {first_bot.name}: {e}")
            # create list of bots in speaking order: first_bot, then others (excluding first)
            order = [first_bot] + [b for b in bots.values() if b is not first_bot]
            last_speaker = first_bot.name
            for other in order:
                if other.name == last_speaker:
                    continue

            # Each bot decides whether to speak. We force first_bot to respond.
            for bot in order:
                # Build context and craft a prompt for the bot
                context = build_context_for_bot()
                # We give short instruction to respond as themselves and optionally refer to names
                prompt = f"You are {bot.name}. Respond naturally based on the conversation below. Refer to other participants by name when appropriate. Be concise but natural.\n\n{context}\n\n{bot.name}, your response:" 

                # Primary bot always replies; others may decide based on relevance
                should_respond = (bot is first_bot)
                if not should_respond:
                    # naive relevance check: if bot's name mentioned in recent utterances OR a question tag like 'I agree' 'I disagree' etc.
                    recent_text = " ".join([u["text"] for u in shared_conversation[-3:]])
                    if regex.search(r"\b" + regex.escape(bot.name) + r"\b", recent_text, flags=regex.IGNORECASE):
                        should_respond = True
                    # also allow some probability of chiming in (here deterministic: join if keyword present)
                    elif regex.search(r"\bagree\b|\bdisagree\b|\bthink\b|\bbut\b", recent_text, flags=regex.IGNORECASE):
                        should_respond = True

                if not should_respond:
                    continue

                # Generate the response (this is a network call; blocking until response is received)
                try:
                    resp = bot.generate_response(prompt)
                    bot_text = resp.text
                    # Clean text
                    bot_text = regex.sub(r"\s*/\s*", "", bot_text)
                    bot_text = regex.sub(r"\*", "", bot_text)
                    bot_text = regex.sub(r'\\"', '"', bot_text)
                    bot_text = regex.sub(r"\\'", "'", bot_text)
                    bot_text = preprocess_text(bot_text)

                    # Log and print
                    shared_conversation.append({"speaker": bot.name, "text": bot_text, "time": datetime.now(timezone.utc).isoformat()})
                    bot.last_spoke = datetime.now(timezone.utc)
                    print_bot(bot.name, bot_text)

                    # Speak sequentially
                    await speak_text(bot_text, bot.voice)

                    # Save bot history
                    bot.save_history()

                except Exception as e:
                    print(f"⚠️ Error generating response for {bot.name}: {e}")

            # After bots have had their opportunity to speak, loop back for user input

        except KeyboardInterrupt:
            print("\n👋 Interrupted — exiting.")
            break
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except Exception as e:
        print(f"Fatal error: {e}")
