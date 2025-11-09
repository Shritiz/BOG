# -*- coding: utf-8 -*-
"""
Main.py - Multi-Bot Conversational System
"""
# === Imports & Initialization ===
import os, glob, json, base64, tempfile, shutil, subprocess, asyncio, random
import importlib.util
import google.generativeai as genai
import edge_tts
import re as regex
import regex as re
from playsound import playsound
from dependancy.input_audio import load_model, get_voice_input
from settings.settings import *  # Import global settings (e.g., VOICE_SETTING, Stream_TTS_Setting)

# === Setup Google Gemini API ===
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))  # Configure API key:contentReference[oaicite:0]{index=0}

# === Initialize Audio Model (VOSK) for voice input ===
base_dir = os.path.dirname(os.path.abspath(__file__))
VOSK_MODEL_PATH = os.path.join(base_dir, "vosk-model-small-en-us-0.15")
if not os.path.exists(VOSK_MODEL_PATH):
    alt_path = os.path.join(os.getcwd(), "vosk-model-small-en-us-0.15")
    if os.path.exists(alt_path):
        VOSK_MODEL_PATH = alt_path
    else:
        print(f"⚠️ Vosk model not found at {VOSK_MODEL_PATH} or {alt_path}")
load_model(VOSK_MODEL_PATH)

# === Prepare Memory Directory ===
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
MEMORY_DIR = os.path.join(DOCUMENTS_DIR, "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

# === Load Bot Characters Dynamically ===
bot_info = {}  # {bot_name: {"description":..., "voice":..., "chat":...}}
characters_dir = os.path.join(os.path.dirname(__file__), "settings", "characters")
for file in glob.glob(os.path.join(characters_dir, "*.py")):
    if file.endswith("__init__.py"):
        continue
    try:
        spec = importlib.util.spec_from_file_location("char_module", file)
        char_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(char_module)
    except Exception as e:
        print(f"⚠️ Could not load character file {file}: {e}")
        continue
    try:
        name = char_module.CHARACTER_NAME
        description = char_module.CHARACTER_DESCRIPTION
        model_name = char_module.MODEL_NAME
    except AttributeError:
        print(f"⚠️ Invalid character file (missing fields): {file}")
        continue
    voice = getattr(char_module, "MODEL_VOICE", "en-US-GuyNeural")
    # Load chat history for this bot
    history_file = os.path.join(MEMORY_DIR, f"{name.lower().replace(' ', '_')}_history.json")
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                history = [{"role": msg["role"], "parts": [{"text": msg["content"]}]} for msg in data]
        except Exception:
            print(f"⚠️ Error loading history for {name} — starting fresh.")
            history = []
    else:
        history = []
    # Initialize Gemini chat session for this bot
    model = genai.GenerativeModel(
        model_name,
        system_instruction=description,
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )
    chat = model.start_chat(history=history)
    bot_info[name] = {"description": description, "voice": voice, "chat": chat}

if not bot_info:
    print("⚠️ No active bots loaded. Please check settings/characters.")
    exit(1)
active_bots = list(bot_info.keys())

# === Preprocessing for pronunciation and symbols ===
SYMBOLS = {"∆": "delta ", "±": "plus or minus ", "°": " degrees ", "µ": "micro ", "Ω": "ohm "}
PRONUNCIATION_FIXES = {
    "NaCl": "sodium chloride", "H2O": "water", "CO2": "carbon dioxide",
    "H2": "hydrogen", "ΔH": "delta H", "μm": "micrometer",
}
def preprocess_text(raw: str) -> str:
    if not raw.strip():
        return ""
    # Normalize whitespace and punctuation
    text = raw.replace("\r", " ").replace("\n", " ")
    text = regex.sub(r'\s+', ' ', text)
    text = regex.sub(r'([.!?])', r'\1 ', text)
    # Replace known symbols/abbreviations
    for sym, word in SYMBOLS.items():
        text = text.replace(sym, word)
    for k, v in PRONUNCIATION_FIXES.items():
        text = regex.sub(re.escape(k), v, text)
    # Common numeric formatting
    text = regex.sub(r'(\d)%', r'\1 percent', text)
    text = regex.sub(r'\$(\d+(\.\d+)?)', r'\1 dollars', text)
    text = regex.sub(r'(\d+):(\d+)', r'\1 ratio \2', text)
    text = regex.sub(r'\bvs\b', 'versus', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bvs\.\b', 'versus', text, flags=regex.IGNORECASE)
    return text.strip()

# === Text-to-Speech (Edge-TTS) ===
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
                    except:
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
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
        await prod_task
        if player:
            player.wait()
        else:
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    finally:
        try:
            os.remove(tmp_path)
        except:
            pass

STREAM_TTS = Stream_TTS_Setting
async def speak(bot_name: str, text: str):
    voice = bot_info[bot_name]["voice"]
    if STREAM_TTS:
        await stream_tts(text, voice)
    else:
        tts = edge_tts.Communicate(text, voice)
        filename = f"{bot_name.replace(' ', '_')}_response.mp3"
        await tts.save(filename)
        playsound(filename)
        try:
            os.remove(filename)
        except:
            pass

# === Save history utility ===
def save_history(bot_name: str, history):
    file_path = os.path.join(MEMORY_DIR, f"{bot_name.lower().replace(' ', '_')}_history.json")
    serializable = []
    for msg in history:
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "role", "")
            parts = getattr(msg, "parts", [])
            content = " ".join([p.text for p in parts if hasattr(p, "text")])
        serializable.append({"role": role, "content": content})
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Failed to save history for {bot_name}: {e}")

# === Conversation Loop ===
def main():
    print(f"🤖 Multi-bot system ready with bots: {', '.join(active_bots)}. Type 'exit' or 'quit' to stop.\n")
    voice_mode = VOICE_SETTING
    context_buffer = []
    while True:
        
        columns = shutil.get_terminal_size().columns
        try:
            # Get user input (voice or text)
            if voice_mode:
                user_input = get_voice_input("🎙️ Press Alt+P to speak your message...")
                print("="*columns)
                print(f"You: {user_input}")
            else:
                user_input = input("You: ").strip()
            if not user_input:
                print("⚠️ No input detected. Please try again.")
                continue
            if user_input.lower() in {"exit", "quit"}:
                print("👋 Conversation ended.")
                break
            context_buffer.append(("User", user_input))
            # Determine which bot to respond first
            mentioned_bot = None
            lower_input = user_input.lower()
            for bot_name in active_bots:
                if bot_name.lower() in lower_input:
                    mentioned_bot = bot_name
                    break
            if mentioned_bot:
                first_bot = mentioned_bot
            else:
                first_bot = random.choice(active_bots)
            responded = {first_bot}
            # First bot response
            try:
                response = bot_info[first_bot]["chat"].send_message(user_input)  # Gemini chat API:contentReference[oaicite:1]{index=1}
                reply = response.text
            except Exception as e:
                print(f"⚠️ Error with {first_bot}: {e}")
                continue
            # Clean and preprocess reply
            reply = regex.sub(r'\s*/\s*', '', reply)
            reply = regex.sub(r'\*', '', reply)
            reply = regex.sub(r'["]', '"', reply)
            reply = preprocess_text(reply)
            print(f"{first_bot}: {reply}")
            # Speak the reply
            try:
                asyncio.run(speak(first_bot, reply))
            except Exception as e:
                print(f"⚠️ TTS error for {first_bot}: {e}")
            context_buffer.append((first_bot, reply))
            save_history(first_bot, bot_info[first_bot]["chat"].history)
            # Check other bots for context triggers
            combined = (user_input + " " + reply).lower()
            triggers = ["agree", "disagree", "think"]
            for bot_name in active_bots:
                if bot_name in responded:
                    continue
                if bot_name.lower() in combined or any(t in combined for t in triggers):
                    responded.add(bot_name)
                    try:
                        response2 = bot_info[bot_name]["chat"].send_message(user_input)
                        reply2 = response2.text
                    except Exception as e:
                        print(f"⚠️ Error with {bot_name}: {e}")
                        continue
                    reply2 = regex.sub(r'\s*/\s*', '', reply2)
                    reply2 = regex.sub(r'\*', '', reply2)
                    reply2 = regex.sub(r'["]', '"', reply2)
                    reply2 = preprocess_text(reply2)
                    print("="*columns)
                    print(f"{bot_name}: {reply2}")
                    try:
                        asyncio.run(speak(bot_name, reply2))
                    except Exception as e:
                        print(f"⚠️ TTS error for {bot_name}: {e}")
                    context_buffer.append((bot_name, reply2))
                    save_history(bot_name, bot_info[bot_name]["chat"].history)
            print("")  # Spacer between turns
        except KeyboardInterrupt:
            print("\n👋 Conversation interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"⚠️ An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
