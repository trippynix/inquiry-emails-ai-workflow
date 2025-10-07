import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from thefuzz import process as fuzzy_process

from src.utils.email_parser_helpers import (
    clean_email_body,
    generate_email_id,
    parse_quantity,
)

# --- Constants and Configuration ---
# Confidence thresholds for fuzzy matching products.
# A match score above HIGH_CONFIDENCE is considered a certain match.
# A score between HIGH_CONFIDENCE and MEDIUM_CONFIDENCE is considered ambiguous.
# A score below MEDIUM_CONFIDENCE is considered an unknown product.
HIGH_CONFIDENCE_THRESHOLD = 90
MEDIUM_CONFIDENCE_THRESHOLD = 75

# --- Core Parsing Logic ---


class EmailParser:
    """
    A class to parse raw email text files, extract structured information,
    and identify any gaps that prevent quoting.
    """

    def __init__(self, price_list: Dict[str, Any]):
        if not price_list:
            raise ValueError("Price list cannot be empty.")
        self.price_list = price_list
        self.product_names = list(price_list.keys())

    def parse_sender(self, content: str) -> Dict[str, Optional[str]]:
        """
        Extracts sender's name and email address.
        It first checks the 'From:' line. If a name is not found there,
        it searches for a name in the signature block of the email.
        """
        # Default sender info
        sender_info = {"name": None, "email": "unknown@example.com"}

        # 1. First, try to parse from the 'From:' header (most reliable source)
        header_match = re.search(
            r"^From:\s*(.*?)\s*<([^>]+)>|^From:\s*([^\s@]+@[^\s@]+\.[^\s@]+)",
            content,
            re.MULTILINE,
        )
        if header_match:
            if header_match.group(1) and header_match.group(2):  # Name and email format
                sender_info["name"] = header_match.group(1).strip()
                sender_info["email"] = header_match.group(2).strip()
            elif header_match.group(3):  # Email only format
                sender_info["email"] = header_match.group(3).strip()

        # 2. If the name is still missing from the header, search the signature
        if not sender_info["name"]:
            # Find the signature block after common sign-offs
            sign_off_pattern = (
                r"\b(Best regards|Sincerely|Thank you|Thanks|Cheers|Regards|Best)\b"
            )
            parts = re.split(sign_off_pattern, content, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) > 1:
                # The signature is the last part of the split
                signature_block = parts[-1]
                # Find the first non-empty line, which is likely the name
                signature_lines = [
                    line.strip()
                    for line in signature_block.splitlines()
                    if line.strip()
                ]
                if signature_lines:
                    for i in range(len(signature_lines)):
                        potential_name = signature_lines[i].strip(
                            ",- "
                        )  # remove trailing noise
                        # A simple validation to ensure it looks like a name
                        if (
                            len(potential_name) > 1
                            and len(potential_name.split()) <= 2
                            and not any(c in potential_name for c in "@<>")
                        ):
                            sender_info["name"] = potential_name

        return sender_info

    def parse_subject(self, content: str) -> str:
        """Extracts the subject from the 'Subject:' line."""
        match = re.search(r"^Subject:\s*(.*)", content, re.MULTILINE)
        return match.group(1).strip() if match else "No Subject"

    def extract_items(self, body: str) -> Tuple[List[Dict], List[Dict]]:
        """
        The core "AI" logic. Extracts products and quantities from the email body.
        It uses fuzzy matching on n-grams (sequences of words, including trigrams)
        to link mentioned items to the official price list, resolving overlaps to
        find the best matches.
        """
        items = []
        gaps = []

        # 1. Generate all possible n-grams with their start/end character positions
        max_n = max(len(p.split()) for p in self.product_names) + 1
        word_tokens = list(re.finditer(r"\S+", body))

        ngrams = []
        for n in range(1, max_n + 1):
            for i in range(len(word_tokens) - n + 1):
                start_token, end_token = word_tokens[i], word_tokens[i + n - 1]
                ngram_text = body[start_token.start() : end_token.end()]
                span = (start_token.start(), end_token.end())
                ngrams.append({"text": ngram_text, "span": span})

        # 2. Score all n-grams against the product list
        scored_matches = []
        for ngram in ngrams:
            if len(ngram["text"]) < 4:  # Skip very short, likely common words
                continue
            match, score = fuzzy_process.extractOne(ngram["text"], self.product_names)
            if score >= MEDIUM_CONFIDENCE_THRESHOLD:
                scored_matches.append(
                    {
                        "text": ngram["text"],
                        "span": ngram["span"],
                        "product": match,
                        "score": score,
                        "length": len(ngram["text"]),
                    }
                )

        # 3. Resolve overlapping matches by preferring higher scores and longer text
        scored_matches.sort(key=lambda x: (x["score"], x["length"]), reverse=True)
        final_matches = []
        used_indices = set()

        for match in scored_matches:
            is_overlapping = False
            match_start, match_end = match["span"]
            for i in range(match_start, match_end):
                if i in used_indices:
                    is_overlapping = True
                    break

            if not is_overlapping:
                final_matches.append(match)
                for i in range(match_start, match_end):
                    used_indices.add(i)

        # 4. Extract quantities for each final, non-overlapping match
        for match in final_matches:
            # Define a search window (e.g., 50 chars before) to find a quantity
            window_start = max(0, match["span"][0] - 50)
            search_window = body[window_start : match["span"][0]]
            quantity = parse_quantity(search_window)

            # 5. Build the final structured output
            item_data = {
                "product_name": None,
                "mentioned_as": match["text"],
                "quantity": quantity,
                "confidence": {"product": 0.0, "quantity": 1.0 if quantity else 0.0},
            }
            score = match["score"]
            product = match["product"]
            if score >= HIGH_CONFIDENCE_THRESHOLD:
                item_data["product_name"] = product
                item_data["confidence"]["product"] = round(score / 100, 2)
                if not quantity:
                    gaps.append(
                        {
                            "type": "MISSING_QUANTITY",
                            "details": f"Product '{product}' was identified, but no quantity was found nearby.",
                        }
                    )
            else:  # Ambiguous match
                item_data["confidence"]["product"] = round(score / 100, 2)
                gaps.append(
                    {
                        "type": "AMBIGUOUS_PRODUCT",
                        "details": f"Request '{match['text']}' is ambiguous. Best guess: '{product}' (Score: {score}).",
                    }
                )
            items.append(item_data)

        if not items and not gaps:
            gaps.append(
                {
                    "type": "UNKNOWN_PRODUCT",
                    "details": f"No product was matched to any known product.",
                }
            )
        return items, gaps

    def parse_email(self, email_content: str) -> Dict[str, Any]:
        """
        Orchestrates the parsing of a single email's content.
        """
        email_id = generate_email_id(email_content)
        sender = self.parse_sender(email_content)
        subject = self.parse_subject(email_content)

        # Extract the main body of the email (text after the headers)
        body_content = re.split(r"\n\s*\n", email_content, 1)[-1]
        cleaned_body = clean_email_body(body_content)

        extracted_items, gaps_identified = self.extract_items(cleaned_body)
        # Final structured data event
        parsed_event = {
            "email_id": email_id,
            "sender": sender,
            "subject": subject,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "extracted_items": extracted_items,
            "currency_mentioned": None,  # Placeholder for future implementation
            "gaps_identified": gaps_identified,
        }

        return parsed_event
