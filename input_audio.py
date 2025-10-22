import sounddevice as sd
import vosk
import queue
import json
import threading
import keyboard
import time

# Global variables
_model = None
_recognizer = None
_stream = None
_recording = False
_transcribed_text = ""
_q = queue.Queue()

# -----------------------
# Internal callback for audio
# -----------------------
def _callback(indata, frames, time_info, status):
    if _recording:
        _q.put(bytes(indata))

# -----------------------
# Load Vosk model
# -----------------------
def load_model(model_path=r"vosk-model-small-en-us-0.15"):
    global _model, _recognizer
    print(f"Loading Vosk model from '{model_path}'...")
    _model = vosk.Model(model_path)
    _recognizer = vosk.KaldiRecognizer(_model, 16000)
    print("✅ Model loaded successfully.")

def toggle_recording():
    global _recording
    _recording = not _recording
    if _recording:
        print("🎧 Recording started...")
    else:
        print("🛑 Recording stopped.")

# -----------------------
# Start microphone stream
# -----------------------
def start_stream():
    global _stream
    if _stream is None:
        _stream = sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=_callback
        )
        _stream.start()

# -----------------------
# Stop microphone stream
# -----------------------
def stop_stream():
    global _stream
    if _stream:
        _stream.stop()
        _stream = None

# -----------------------
# Record voice and return transcription
# -----------------------
def get_voice_input(prompt="🎙️ Press Alt+P to start/stop recording your message..."):
    global _recording, _transcribed_text

    _transcribed_text = ""
    print(prompt)
    start_stream()
    keyboard.add_hotkey("alt+p", toggle_recording)
    while not _recording:
        time.sleep(0.1)
    while _recording or not _q.empty():
        if not _q.empty():
            data = _q.get()
            if _recognizer.AcceptWaveform(data):
                result = json.loads(_recognizer.Result())
                _transcribed_text += " " + result.get("text", "")
        else:
            time.sleep(0.05)
    final = json.loads(_recognizer.FinalResult())
    _transcribed_text += " " + final.get("text", "")
    _transcribed_text = _transcribed_text.strip()

    return _transcribed_text
