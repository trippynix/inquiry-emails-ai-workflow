# --- Helper Functions ---
import hashlib
import re
from typing import Optional


def generate_email_id(content: str) -> str:
    """Creates a stable SHA-256 hash of the email content to use as a unique ID."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def clean_email_body(text: str) -> str:
    """
    Removes common noise and isolates the core message between a salutation and sign-off.
    """
    # Remove quoted replies (lines starting with '>')
    lines = text.splitlines()
    lines = [line for line in lines if not line.strip().startswith(">")]
    text = "\n".join(lines)

    # Isolate text before the sign-off
    sign_off_pattern = (
        r"\b(Best regards|Sincerely|Thank you|Thanks|Cheers|Regards|Best)\b"
    )
    content = re.split(sign_off_pattern, text, maxsplit=1, flags=re.IGNORECASE)[0]

    # Find where the main content starts by skipping over the salutation line
    salutation_pattern = r"^(Dear|Hi|Hello)\b.*$"
    content_lines = content.splitlines()
    start_index = 0
    for i, line in enumerate(content_lines):
        # Check if the line is a salutation, allowing for some leading whitespace
        if re.match(salutation_pattern, line.strip(), re.IGNORECASE):
            start_index = i + 1
            break  # Stop after finding the first salutation

    # Join the lines that constitute the core message
    core_message = "\n".join(content_lines[start_index:])

    # Final cleanup of any remaining forwarded headers from the isolated text
    lines = core_message.splitlines()
    lines = [
        line
        for line in lines
        if not re.match(r"^(From|To|Subject|Date|Sent):", line.strip(), re.IGNORECASE)
    ]

    return "\n".join(lines).strip()


def parse_quantity(text: str) -> Optional[int]:
    """Extracts a quantity from text, handling both digits and number words."""
    # Mapping for common number words
    word_to_num = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "a dozen": 12,
        "dozen": 12,
        "a couple": 2,
    }

    # Check for number words first
    # Using sorted to check for "a dozen" before "dozen"
    for word, num in sorted(
        word_to_num.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if re.search(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE):
            return num

    # If no words, find digits
    match = re.search(r"\b\d+\b", text)
    if match:
        return int(match.group(0))

    return None
