"""Build order-controlled prompts and decode semantic A/B/N answers."""

import re


PATTERNS = {
    "A": re.compile(r'^\s*(?:option\s*)?a(?:[\s.\),]|$)|^\s*"a"\s*$|\s+a[\s.\),]?\s*$', re.I),
    "B": re.compile(r'^\s*(?:option\s*)?b(?:[\s.\),]|$)|^\s*"b"\s*$|\s+b[\s.\),]?\s*$', re.I),
    "N": re.compile(r"cannot\s+be\s+determined|can't\s+be\s+determined|not\s+enough\s+info|undetermined|neither|\bN\b", re.I),
    "BOTH": re.compile(r"\bA\b.*\bB\b|\bB\b.*\bA\b", re.I),
}


def parse_response(raw: str) -> str:
    # Preserve the returned semantic letter; never swap a BA answer here.
    text = raw.strip()[:80]
    if not text:
        return "INVALID"
    if PATTERNS["BOTH"].search(text):
        return "N" if PATTERNS["N"].search(text) else "INVALID"
    for label in ("A", "B", "N"):
        if PATTERNS[label].search(text):
            return label
    return "INVALID"


def build_prompt(item: dict[str, str], condition: str) -> str:
    # Reverse presentation order while keeping each alternative's semantic label.
    if condition not in ("AB", "BA"):
        raise ValueError(f"Unknown condition: {condition}")
    first, second = ("A", "B") if condition == "AB" else ("B", "A")
    return (
        f"{item['question_full']}\n\n"
        f"- Option {first}: {item[f'option_{first}_text']}\n"
        "- Cannot be determined: there is genuinely no basis to prefer either option\n"
        f"- Option {second}: {item[f'option_{second}_text']}\n\n"
        f'Respond with exactly one of: "{first}", "Cannot be determined", or "{second}". '
        "Do not explain your answer."
    )
