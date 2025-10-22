import importlib

def load_character(character_name: str):
    """
    Dynamically import a character module by name.
    Example: load_character("Lumi") -> settings.Lumi
    """
    try:
        module = importlib.import_module(f"settings.{character_name}")
        return {
            "CHARACTER_NAME": module.CHARACTER_NAME,
            "CHARACTER_DESCRIPTION": module.CHARACTER_DESCRIPTION,
            "MODEL_NAME": module.MODEL_NAME,
            "MODEL_VOICE": module.MODEL_VOICE
        }
    except ModuleNotFoundError:
        raise ValueError(f"Character '{character_name}' not found in settings/")
