import google.generativeai as genai
import json, os, edge_tts, asyncio, subprocess, unicodedata
from playsound import playsound
import shutil
import re as regex
from input_audio import load_model, get_voice_input
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
CHARACTER = load_character("Martin")  # Change the character name here to switch characters
CHARACTER_NAME = CHARACTER["CHARACTER_NAME"]
CHARACTER_DESCRIPTION = CHARACTER["CHARACTER_DESCRIPTION"]
MODEL_NAME = CHARACTER["MODEL_NAME"]
try:
    MODEL_VOICE = CHARACTER["MODEL_VOICE"]
except KeyError:
    MODEL_VOICE = "en-US-GuyNeural"


# === Setup API Key ===
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# === File Paths ===
MEMORY_DIR = os.path.join(os.getcwd(), "memory")
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

def preprocess_text(raw: str) -> str:
    if not raw.strip():
        return ""
    text = unicodedata.normalize("NFKC", raw)
    for symbol, word in SYMBOLS.items():
        text = text.replace(symbol, word)
    for k, v in PRONUNCIATION_FIXES.items():
        text = text.replace(k, v)
    text = regex.sub(r'(\w)-(\w)', r'\1  \2', text)
    text = regex.sub(r'(\d)\s*-\s*(\d)', r'\1 minus \2', text)
    text = regex.sub(r'(\d)\.(\d)', r'\1 point \2', text)
    text = regex.sub(r'(\d+)-(\d+)', r'\1 to \2', text)
    text = regex.sub(r'(\d+)%', r'\1 percent', text)
    text = regex.sub(r'(\d+)\s*-\s*(\d+)', r'\1 to \2', text)
    text = regex.sub(r'(\d+)\s*%', r'\1 percent', text)
    text = regex.sub(r'(\d+)(st|nd|rd|th)\b', r'\1 \2', text) 
    text = regex.sub(r'\$(\d+)', r'\1 dollars', text)
    text = regex.sub(r'(\d+)\s*\$', r'\1 dollars', text)
    text = regex.sub(r'(\d+):(\d+)', r'\1 ratio \2', text)
    text = regex.sub(r'(\d+)\s*:\s*(\d+)', r'\1 ratio \2', text)
    text = regex.sub(r'(\d+)-(\d+)-(\d+)', r'\1 dash \2 dash \3', text)  # Dates like 2023-10-05
    text = regex.sub(r'(\d+)\s*-\s*(\d+)\s*-\s*(\d+)', r'\1 dash \2 dash \3', text)
    text = regex.sub(r'\₹(\d+)', r'\1 rupees', text)
    text = regex.sub(r'(\d+)\s*\₹', r'\1 rupees', text)
    text = regex.sub(r'\€(\d+)', r'\1 euros', text)
    text = regex.sub(r'(\d+)\s*\€', r'\1 euros', text)
    text = regex.sub(r'\£(\d+)', r'\1 pounds', text)
    text = regex.sub(r'(\d+)\s*\£', r'\1 pounds', text)
    text = regex.sub(r'(\d+)\s*\/\s*(\d+)', r'\1 over \2', text)  # Fractions like 3/4
    text = regex.sub(r'(\d+)\/(\d+)', r'\1 over \2', text)
    text = regex.sub(r'\bvs\b', 'versus', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\betc\b', 'et cetera', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bi\.e\.\b', 'that is', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\be\.g\.\b', 'for example', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bMr\.\b', 'Mister', text)
    text = regex.sub(r'\bMrs\.\b', 'Misses', text)
    text = regex.sub(r'\bDr\.\b', 'Doctor', text)
    text = regex.sub(r'\bSt\.\b', 'Saint', text)
    text = regex.sub(r'\bProf\.\b', 'Professor', text)
    text = regex.sub(r'\bInc\.\b', 'Incorporated', text)
    text = regex.sub(r'\bLtd\.\b', 'Limited', text)
    text = regex.sub(r'\bCo\.\b', 'Company', text)
    text = regex.sub(r'\bJr\.\b', 'Junior', text)
    text = regex.sub(r'\bSr\.\b', 'Senior', text)
    text = regex.sub(r'\bvs\.\b', 'versus', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bJan\.\b', 'January', text)
    text = regex.sub(r'\bFeb\.\b', 'February', text)
    text = regex.sub(r'\bMar\.\b', 'March', text)
    text = regex.sub(r'\bApr\.\b', 'April', text)
    text = regex.sub(r'\bJun\.\b', 'June', text)
    text = regex.sub(r'\bJul\.\b', 'July', text)
    text = regex.sub(r'\bAug\.\b', 'August', text)
    text = regex.sub(r'\bSep\.\b', 'September', text)
    text = regex.sub(r'\bOct\.\b', 'October', text)
    text = regex.sub(r'\bNov\.\b', 'November', text)
    text = regex.sub(r'\bDec\.\b', 'December', text)
    text = regex.sub(r'\bkm\b', 'kilometers', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bcm\b', 'centimeters', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bmm\b', 'millimeters', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bkg\b', 'kilograms', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bg\b', 'grams', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bmg\b', 'milligrams', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\blb\b', 'pounds', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bft\b', 'feet', text, flags=regex.IGNORECASE)
    #text = regex.sub(r'\bin\b', 'inches', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bhrs\b', 'hours', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bhr\b', 'hour', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bmin\b', 'minutes', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bsec\b', 'seconds', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bvs\b', 'versus', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bapprox\b', 'approximately', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bdept\b', 'department', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\btemp\b', 'temperature', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bqty\b', 'quantity', text, flags=regex.IGNORECASE)
    text = regex.sub(r'\bno\b', 'number', text, flags=regex.IGNORECASE)
    text = text.replace("\r", "").replace("\n", " ")
    text = regex.sub(r'\s+', ' ', text)
    text = regex.sub(r'([.,;!?])', r'\1 ', text)
    return text.strip()

# === Stream TTS ===
async def stream_tts(text: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    process = subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            process.stdin.write(chunk["data"])
            process.stdin.flush()
    process.stdin.close()
    process.wait()

# === Initialize TTS ===
STREAM_TTS = Stream_TTS_Setting  
async def speak(text):
    voice = MODEL_VOICE
    if STREAM_TTS:
        await stream_tts(text, voice)
        return
    else:
        tts = edge_tts.Communicate(text, voice)
        await tts.save(f"{CHARACTER_NAME}_response.mp3")
        playsound(f"{CHARACTER_NAME}_response.mp3")

        if os.path.exists(f"{CHARACTER_NAME}_response.mp3"):
            os.remove(f"{CHARACTER_NAME}_response.mp3")

# === Initialize Chat ===
columns = shutil.get_terminal_size().columns
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

    chat = model.start_chat(history=history)
    print(f"🤖 {CHARACTER_NAME} is ready! Type 'exit' or 'quit' to stop.\n")
    #print("Press Alt+P to start/stop recording. Press Esc to quit.")
    #print("press 'p' to pause/resume, 's' to stop")
    print("=" * columns,"\n")
    voice = VOICE_SETTING
    while True:
        try:
            print("=" * columns,"\n")
            #user_input = input("You: ").strip()
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
            cresponse = regex.sub(r'\s*/\s*', '', cresponse)
            cresponse = regex.sub(r'\s*/\s*', '', cresponse)
            cresponse = regex.sub(r'\*', '', cresponse)
            cresponse = regex.sub(r'/"', '"', cresponse)
            cresponse = regex.sub(r"/'", "'", cresponse)
            cresponse = regex.sub(r'###', '"""', cresponse)
            cresponse = regex.sub(r'\\\\\\', '', cresponse)
            cresponse = regex.sub(r'\\"', '"', cresponse)
            cresponse = regex.sub(r"\\'", "'", cresponse)
            cresponse = preprocess_text(cresponse)
            print("=" * columns,"\n")
            print(f"{CHARACTER_NAME}: {cresponse}\n")
            asyncio.run(speak(cresponse))
            save_history(chat.history)
        except KeyboardInterrupt:
            print("\n👋 Chat interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"⚠️ An error occurred: {e}")
if __name__ == "__main__":
    main()