from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LANG_DIR = _PROJECT_ROOT / "lang"
_INSTRUCTIONS_DIR = _PROJECT_ROOT / "instructions"
_CHANNELS_FILE = _PROJECT_ROOT / "channels.json"
_CONFIG_FILE = _PROJECT_ROOT / "config.yml"

DEFAULT_CONFIG = {
    "LANGUAGE": "en",
    "INTERNET_ACCESS": False,
    "API_BASE_URL": "https://api.openai.com/v1",
    "MODEL_ID": "gpt-4o-mini",
}

DEFAULT_LANGUAGE = {
    "language_name": "English",
    "instruc_image_caption": "Image captions:",
    "pfp": "Change bot's profile picture using an image URL",
    "pfp_change_msg_1": "Please provide an image URL or attachment.",
    "pfp_change_msg_2": "Profile picture changed successfully.",
    "ping": "PONG! Provide bot latency",
    "ping_msg": "Pong! Latency: ",
    "changeusr": "Change bot's username",
    "changeusr_msg_1": "Trying to change username....",
    "changeusr_msg_2_part_1": "Sorry, the username '",
    "changeusr_msg_2_part_2": "' is already taken.",
    "changeusr_msg_3": "Username changed to ",
    "toggledm": "Toggle DM for chatting",
    "toggleactive": "Toggle active channels",
    "toggleactive_msg_1": "has been removed from the list of active channels.",
    "toggleactive_msg_2": "has been added to the list of active channels!",
    "help": "Get all other commands!",
    "help_footer": "",
    "nekos": "Display a random image or GIF",
    "nekos_msg": "Invalid category provided. Valid categories are: ",
    "imagine": "Generate an image",
    "imagine_msg": "Finished image generation!",
    "bonk": "Clear message",
    "bonk_msg": "Message history has been cleared!",
}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


config = DEFAULT_CONFIG.copy()
if _CONFIG_FILE.exists():
    with open(_CONFIG_FILE, "r", encoding="utf-8") as config_file:
        config.update(yaml.safe_load(config_file) or {})

config["LANGUAGE"] = os.getenv("LANGUAGE", str(config["LANGUAGE"]))
config["INTERNET_ACCESS"] = _env_bool("INTERNET_ACCESS", bool(config["INTERNET_ACCESS"]))
config["API_BASE_URL"] = os.getenv("API_BASE_URL", str(config["API_BASE_URL"]))
config["MODEL_ID"] = os.getenv("MODEL_ID", str(config["MODEL_ID"]))

valid_language_codes: list[str] = []
current_language_code = str(config["LANGUAGE"] or "en")

if _LANG_DIR.is_dir():
    for path in _LANG_DIR.glob("lang.*.json"):
        if path.is_file():
            valid_language_codes.append(path.stem.split(".", 1)[1])

if "en" not in valid_language_codes:
    valid_language_codes.append("en")


def load_current_language() -> dict:
    candidates = [current_language_code]
    if current_language_code != "en":
        candidates.append("en")

    for code in candidates:
        lang_file_path = _LANG_DIR / f"lang.{code}.json"
        if not lang_file_path.is_file():
            continue
        try:
            with open(lang_file_path, encoding="utf-8") as lang_file:
                return json.load(lang_file)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not read %s: %s", lang_file_path, exc)

    log.warning(
        "Language file missing for %r — using built-in English defaults. Expected path: %s",
        current_language_code,
        _LANG_DIR / f"lang.{current_language_code}.json",
    )
    return DEFAULT_LANGUAGE.copy()


def load_instructions() -> dict:
    instructions: dict[str, str] = {}
    if not _INSTRUCTIONS_DIR.is_dir():
        return instructions
    for file_path in _INSTRUCTIONS_DIR.glob("*.txt"):
        try:
            instructions[file_path.stem] = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("Could not read instruction file %s: %s", file_path, exc)
    return instructions


def load_active_channels() -> dict:
    if not _CHANNELS_FILE.exists():
        return {}
    try:
        with open(_CHANNELS_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s: %s", _CHANNELS_FILE, exc)
        return {}