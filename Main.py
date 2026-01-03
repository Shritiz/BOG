import google.generativeai as genai
import json, os, edge_tts, asyncio, subprocess, unicodedata, base64, tempfile
from playsound import playsound
import shutil
import re as regex
from dependancy.input_audio import load_model, get_voice_input
from dependancy.optts_inst import speak_blocking as speak_t1
from dependancy.optts_inst import preprocess_text
import threading
from settings.settings import *
# === Initialize Audio Model===
base_dir = os.path.dirname(os.path.abspath(__file__))
VOSK_MODEL_PATH = os.path.join(base_dir, "vosk-model-small-en-us-0.15")
if not os.path.exists(VOSK_MODEL_PATH):
    alt = os.path.join(os.getcwd(), "vosk-model-small-en-us-0.15")
    if os.path.exists(alt):
        VOSK_MODEL_PATH = alt
    else:
        print(f"⚠️ Vosk model not found at {VOSK_MODEL_PATH} or {alt}")

load_model(VOSK_MODEL_PATH)

# === CHARACTER SELECTION ===
from settings import load_character
CHARACTER = load_character("Sofi")  # Change the character name here to switch characters
CHARACTER_NAME = CHARACTER["CHARACTER_NAME"]
CHARACTER_DESCRIPTION = CHARACTER["CHARACTER_DESCRIPTION"]
MODEL_NAME = CHARACTER["MODEL_NAME"]
try:
    MODEL_VOICE = CHARACTER["MODEL_VOICE"]
except KeyError:
    MODEL_VOICE = "en-US-DavisNeural"


# === Setup API Key ===
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# === File Paths ===
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
MEMORY_DIR = os.path.join(DOCUMENTS_DIR, "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(
    MEMORY_DIR,
    f"{CHARACTER_NAME.lower().replace(' ', '_')}_history.json"
)

# === Load Chat History ===
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [{"role": msg["role"], "parts": [{"text": msg["content"]}]} for msg in data]
    except Exception:
        print("⚠️ Error loading history — starting fresh.")
        return []

# === Save History ===
def save_history(history):
    try:
        serializable = []
        for msg in history:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
            else:
                role = getattr(msg, "role", "unknown")
                content = " ".join([part.text for part in getattr(msg, "parts", []) if hasattr(part, "text")])
            
            serializable.append({"role": role, "content": content})

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print("⚠️ Failed to save history:", e)


# === process text ===
SYMBOLS = {"∆": "delta ", "±": "plus or minus ", "°": " degrees ", "µ": "micro ", "Ω": "ohm "}
PRONUNCIATION_FIXES = {"NaCl": "sodium chloride", "H2O": "water", "CO2": "carbon dioxide","H2": "hydrogen","ΔH": "delta H","μm": "micrometer",}



# === Initialize Chat ===

def main(): 
    history = load_history()    
    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=CHARACTER_DESCRIPTION,
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    )
    columns = shutil.get_terminal_size().columns
    chat = model.start_chat(history=history)
    print(f"🤖 {CHARACTER_NAME} is ready! Type 'exit' or 'quit' to stop.\n")
    print("=" * columns,"\n")
    voice = VOICE_SETTING
    while True:
        try:
            columns = shutil.get_terminal_size().columns
            print("=" * columns,"\n")
            if voice == True:
                user_input = get_voice_input("🎙️ Press Alt+P to start/stop recording your message...")
                print(f"Tappu4421: {user_input}\n")
            else:
                user_input = input("You: ").strip()
            if not user_input:
                print("⚠️ No input detected. Please try again.")
                continue
            if user_input.lower() in {"exit", "quit"}:
                print("Chat ended. Farewell, matey!")
                break
            
            response = chat.send_message(user_input)
            cresponse = response.text
            #cresponse = regex.sub(r'\s*/\s*', '', cresponse)
            #cresponse = regex.sub(r'\s*/\s*', '', cresponse)
            #cresponse = regex.sub(r'\*', '', cresponse)
            #cresponse = regex.sub(r'/"', '"', cresponse)
            #cresponse = regex.sub(r"/'", "'", cresponse)
            #cresponse = regex.sub(r'###', '"""', cresponse)
            #cresponse = regex.sub(r'\\\\\\', '', cresponse)
            #cresponse = regex.sub(r'\\"', '"', cresponse)
            #cresponse = regex.sub(r"\\'", "'", cresponse)
            cresponse = preprocess_text(cresponse)
            print("=" * columns,"\n")
            print(f"{CHARACTER_NAME}: {cresponse}\n")
            #print(f"[DEBUG TTS TEXT] -> {repr(cresponse)}")
            #print(f"[DEBUG LENGTH] -> {len(cresponse.strip())}")
            if cresponse.strip():
                speak_t1(cresponse, voice=MODEL_VOICE)
            else:
                print("⚠️ No response generated to speak.")
            save_history(chat.history)
        except KeyboardInterrupt:
            print("\n👋 Chat interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
if __name__ == "__main__":
    main()
