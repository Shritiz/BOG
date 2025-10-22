import edge_tts
import asyncio

# ---------------------- CONFIG ----------------------
LOCALE = "en-US"               # Language locale filter
GENDER = "female"              # Gender filter
PREFERRED_STYLES = ["cheerful", "friendly", "affectionate", "playful","cute"]  # Add any styles you want
# ----------------------------------------------------

async def list_filtered_voices():
    voices = await edge_tts.list_voices()
    
    # Filter by locale and gender
    filtered = [
        v for v in voices
        if v["Locale"] == LOCALE and v["Gender"].lower() == GENDER.lower()
    ]
    
    # Further filter by preferred styles (if the voice has any of the preferred styles)
    if PREFERRED_STYLES:
        filtered = [
            v for v in filtered
            if any(style.lower() in [s.lower() for s in v.get("StyleList", [])] for style in PREFERRED_STYLES)
        ]
    
    if not filtered:
        print("No voices found matching your filters!")
        return

    # Print results nicely
    print(f"Voices matching locale={LOCALE}, gender={GENDER}, styles={PREFERRED_STYLES}:")
    for i, v in enumerate(filtered, start=1):
        styles = ", ".join(v.get("StyleList", [])) or "None"
        print(f"{i}. {v['Name']} - Styles: {styles}")

if __name__ == "__main__":
    asyncio.run(list_filtered_voices())
