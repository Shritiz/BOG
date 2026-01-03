import optts_inst
from optts_inst import preprocess_text
from optts_inst import speak_blocking
text = "Eheheh~ \"Test 11\" nya? 🤭 Is my Tappu giving Sofi a little quiz, sweetie? My wittle brain might need a hint for this one, teehee~ But I'm ready for any fun test with you! 🥰✨"
cleaned_text = optts_inst.preprocess_text(text)
print(cleaned_text)
    """
    Flush any remaining audio and wait for process to finish.
    """
speak_blocking(text: str, "en-US-SaraNeural"):