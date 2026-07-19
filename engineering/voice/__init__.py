"""
Aego Cyber Cafe Voice Pipeline — Package init.

Maps hyphenated filenames to importable module names.
"""
import importlib
import sys
from pathlib import Path

# Map hyphenated filenames to underscore import names
_ALIASES = {
    "audio_utils": "audio-utils",
    "stt_module": "stt-module",
    "tts_module": "tts-module",
    "wake_word": "wake-word",
    "voice_pipeline": "voice-pipeline",
}

_dir = Path(__file__).parent

for underscore_name, hyphen_name in _ALIASES.items():
    _file = _dir / f"{hyphen_name}.py"
    if _file.exists() and underscore_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(underscore_name, str(_file))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[underscore_name] = mod
            spec.loader.exec_module(mod)
