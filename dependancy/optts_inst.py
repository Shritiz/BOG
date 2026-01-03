import asyncio, keyboard, tempfile, os, threading, re, unicodedata, subprocess
import edge_tts
import clipboard as pyperclip

# --- Available Voices ---
VOICES = {
    "1": ("en-US-JennyNeural", "Jenny (cute EN female)"),
    "2": ("en-US-GuyNeural", "Guy (deep EN male)"),
    "3": ("ja-JP-NanamiNeural", "Nanami (cute JP female)"),
    "4": ("en-GB-SoniaNeural", "Sonia (cute UK female)"),
    "5": ("en-IN-PrabhatNeural", "Prabhat (deep IN male)"),
    "6": ("en-US-AriaNeural", "Aria (cute US female)"),
}

# --- Symbol replacements and pronunciation fixes (same as before, shortened for brevity) ---
SYMBOLS = {"∆": "delta ", "±": "plus or minus ", "°": " degrees ", "µ": "micro ", "Ω": "ohm "}
PRONUNCIATION_FIXES = {"NaCl": "sodium chloride", "H2O": "water", "CO2": "carbon dioxide"}

def preprocess_text(raw: str) -> str:
    if not raw.strip():
        return ""
    text = raw
    # Normalize Unicode visually similar characters
    #text = unicodedata.normalize("NFKC", raw)

    # Replace known symbols
    for symbol, word in SYMBOLS.items():
        text = text.replace(symbol, word)

    # Apply pronunciation fixes
    for k, v in PRONUNCIATION_FIXES.items():
        text = text.replace(k, v)

    # Fix minus/dash usage
    text = re.sub(r'(\d)\s*-\s*(\d)', r'\1 minus \2', text)
    text = re.sub(r'(\w)-(\w)', r'\1 \2', text)
    text = re.sub(r'(\d)\.(\d)', r'\1 point \2', text)
    text = re.sub(r'(\d+)-(\d+)', r'\1 to \2', text)
    text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1 to \2', text)
    text = re.sub(r'(\d+)%', r'\1 percent', text)
    text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
    text = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1 \2', text) 
    text = re.sub(r'\$(\d+)', r'\1 dollars', text)
    text = re.sub(r'(\d+)\s*\$', r'\1 dollars', text)
    text = re.sub(r'(\d+):(\d+)', r'\1 ratio \2', text)
    text = re.sub(r'(\d+)\s*:\s*(\d+)', r'\1 ratio \2', text)
    text = re.sub(r'(\d+)-(\d+)-(\d+)', r'\1 dash \2 dash \3', text)  # Dates like 2023-10-05
    text = re.sub(r'(\d+)\s*-\s*(\d+)\s*-\s*(\d+)', r'\1 dash \2 dash \3', text)
    text = re.sub(r'\₹(\d+)', r'\1 rupees', text)
    text = re.sub(r'(\d+)\s*\₹', r'\1 rupees', text)
    text = re.sub(r'\€(\d+)', r'\1 euros', text)
    text = re.sub(r'(\d+)\s*\€', r'\1 euros', text)
    text = re.sub(r'\£(\d+)', r'\1 pounds', text)
    text = re.sub(r'(\d+)\s*\£', r'\1 pounds', text)
    text = re.sub(r'(\d+)\s*\/\s*(\d+)', r'\1 over \2', text)  # Fractions like 3/4
    text = re.sub(r'(\d+)\/(\d+)', r'\1 over \2', text)
    text = re.sub(r'\bvs\b', 'versus', text, flags=re.IGNORECASE)
    text = re.sub(r'\betc\b', 'et cetera', text, flags=re.IGNORECASE)
    text = re.sub(r'\bi\.e\.\b', 'that is', text, flags=re.IGNORECASE)
    text = re.sub(r'\be\.g\.\b', 'for example', text, flags=re.IGNORECASE)
    text = re.sub(r'\bMr\.\b', 'Mister', text)
    text = re.sub(r'\bMrs\.\b', 'Misses', text)
    text = re.sub(r'\bDr\.\b', 'Doctor', text)
    text = re.sub(r'\bSt\.\b', 'Saint', text)
    text = re.sub(r'\bProf\.\b', 'Professor', text)
    text = re.sub(r'\bInc\.\b', 'Incorporated', text)
    text = re.sub(r'\bLtd\.\b', 'Limited', text)
    text = re.sub(r'\bCo\.\b', 'Company', text)
    text = re.sub(r'\bJr\.\b', 'Junior', text)
    text = re.sub(r'\bSr\.\b', 'Senior', text)
    text = re.sub(r'\bvs\.\b', 'versus', text, flags=re.IGNORECASE)
    text = re.sub(r'\bJan\.\b', 'January', text)
    text = re.sub(r'\bFeb\.\b', 'February', text)
    text = re.sub(r'\bMar\.\b', 'March', text)
    text = re.sub(r'\bApr\.\b', 'April', text)
    text = re.sub(r'\bJun\.\b', 'June', text)
    text = re.sub(r'\bJul\.\b', 'July', text)
    text = re.sub(r'\bAug\.\b', 'August', text)
    text = re.sub(r'\bSep\.\b', 'September', text)
    text = re.sub(r'\bOct\.\b', 'October', text)
    text = re.sub(r'\bNov\.\b', 'November', text)
    text = re.sub(r'\bDec\.\b', 'December', text)
    text = re.sub(r'\bkm\b', 'kilometers', text, flags=re.IGNORECASE)
    text = re.sub(r'\bcm\b', 'centimeters', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmm\b', 'millimeters', text, flags=re.IGNORECASE)
    text = re.sub(r'\bkg\b', 'kilograms', text, flags=re.IGNORECASE)
    text = re.sub(r'\bg\b', 'grams', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmg\b', 'milligrams', text, flags=re.IGNORECASE)
    text = re.sub(r'\blb\b', 'pounds', text, flags=re.IGNORECASE)
    text = re.sub(r'\bft\b', 'feet', text, flags=re.IGNORECASE)
    #text = re.sub(r'\bin\b', 'inches', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhrs\b', 'hours', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhr\b', 'hour', text, flags=re.IGNORECASE)
    text = re.sub(r'\bmin\b', 'minutes', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsec\b', 'seconds', text, flags=re.IGNORECASE)
    text = re.sub(r'\bvs\b', 'versus', text, flags=re.IGNORECASE)
    text = re.sub(r'\bapprox\b', 'approximately', text, flags=re.IGNORECASE)
    text = re.sub(r'\bdept\b', 'department', text, flags=re.IGNORECASE)
    text = re.sub(r'\btemp\b', 'temperature', text, flags=re.IGNORECASE)
    text = re.sub(r'\bqty\b', 'quantity', text, flags=re.IGNORECASE)
    text = re.sub(r'\bno\b', 'number', text, flags=re.IGNORECASE)
    


    # Clean newlines and extra spaces
    text = text.replace("\r", "").replace("\n", " ")
    text = re.sub(r'\s+', ' ', text)

    # Add extra pauses for punctuation to sound smoother
    text = re.sub(r'([.,;!?])', r'\1 ', text)

    return text.strip()

# --- Streaming playback (true live TTS) ---
async def stream_tts(text: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    
    # ffplay reads audio from stdin as it streams
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

# --- Speak clipboard contents ---
def speak_clipboard(voice: str, label: str):
    raw = pyperclip.paste()

    if not raw.strip():
        print("[Clipboard empty]")
        return

    print(f"[{label}] Speaking (streaming): {raw[:80]}{'...' if len(raw) > 80 else ''}")
    speak(raw, voice)

def speak(text: str, voice: str):
    """
    Public TTS function.
    Can be imported and used by other programs.

    Example:
        speak("Hello!", "en-US-JennyNeural")
    """
    if not text or not text.strip():
        return

    clean_text = text

    def task():
        try:
            asyncio.run(stream_tts(clean_text, voice))
        except RuntimeError:
            # If already inside an event loop
            loop = asyncio.get_event_loop()
            loop.create_task(stream_tts(clean_text, voice))
        except Exception as e:
            print(f"[TTS Error] {e}")

    threading.Thread(target=task, daemon=True).start()

def speak_blocking(text: str, voice: str):
    """
    Blocking TTS call.
    Use this in scripts where the program should wait until speech finishes.
    """
    if not text or not text.strip():
        return

    clean_text = re.sub(r'[*_#`~]', '', text)

    try:
        asyncio.run(stream_tts(clean_text, voice))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(stream_tts(clean_text, voice))

# --- Main ---
def main():
    print("[Edge-TTS Smart Reader Ready]")
    print("Hotkeys:")
    for num, (voice, label) in VOICES.items():
        print(f"  Ctrl+Alt+{num} -> {label}")
        keyboard.add_hotkey(f"ctrl+alt+{num}", lambda v=voice, l=label: speak_clipboard(v, l))
    print("  Esc -> Quit")
    keyboard.wait("esc")

if __name__ == "__main__":
    main()
