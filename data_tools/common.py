"""Shared JSONL and language helpers for prompt variant tools."""
import json
from pathlib import Path


TEXT_FIELDS = ("text", "prompt", "prompt_text", "question", "instruction", "input")


def read_jsonl(path):
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: each JSONL row must be an object")
            rows.append(row)
    return rows


def text_field(row):
    for name in TEXT_FIELDS:
        if isinstance(row.get(name), str):
            return name
    raise ValueError("row has no string prompt field; expected one of: " + ", ".join(TEXT_FIELDS))


def language_code(language):
    aliases = {"kannada": "kn", "ಕನ್ನಡ": "kn", "hindi": "hi", "tamil": "ta",
               "telugu": "te", "malayalam": "ml", "bengali": "bn", "marathi": "mr",
               "gujarati": "gu", "punjabi": "pa", "odia": "or", "assamese": "as"}
    code = aliases.get(language.lower(), language.lower())
    if len(code) != 2:
        raise ValueError(f"unsupported language identifier {language!r}; use a language name or ISO code")
    return code


def write_jsonl(path, rows):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
