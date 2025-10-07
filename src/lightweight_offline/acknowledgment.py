import re
from typing import Dict, Any, List


class AcknowledgmentGenerator:
    """
    Generates a professional acknowledgment email draft based on a parsed event.

    The generator confirms the items understood and asks targeted questions
    to resolve any gaps identified during parsing, ensuring that the generated
    text is context-aware and helpful.
    """

    def generate_acknowledgment(self, parsed_event: Dict[str, Any]) -> Dict[str, str]:
        """
        Orchestrates the creation of the acknowledgment draft.

        Args:
            parsed_event: The structured data extracted from the email.

        Returns:
            A dictionary containing the recipient's email, a subject line,
            and the generated email body.
        """
        sender_name = parsed_event.get("sender", {}).get("name")
        gaps = parsed_event.get("gaps_identified", [])
        items = parsed_event.get("extracted_items", [])

        # Construct the email body
        greeting = f"Hi {sender_name}," if sender_name else "Hello,"
        intro = self._generate_intro(items, gaps)
        questions = self._generate_questions(gaps)
        closing = (
            "\n\nWe will prepare a detailed quote for you as soon as we have this information."
            if questions
            else "\n\nWe are preparing a detailed quote for you and will send it over shortly."
        )
        sign_off = "\n\nBest regards,\nKreeda Labs Team"

        body = f"{greeting}\n\n{intro}{questions}{closing}{sign_off}"

        # Structure the final output JSON
        return {
            "recipient_email": parsed_event.get("sender", {}).get("email"),
            "subject": f"Re: {parsed_event.get('subject', 'Your Inquiry')}",
            "body": body.strip(),
        }

    def _generate_intro(
        self, items: List[Dict[str, Any]], gaps: List[Dict[str, Any]]
    ) -> str:
        """Creates the opening paragraph confirming the request."""
        confirmed_items = [
            f"{item['quantity']} x {item['product_name']}"
            for item in items
            if item.get("product_name") and item.get("quantity")
        ]

        if not items:
            return "Thank you for your email. Could you please provide more details about the products you are interested in?"

        intro = "Thank you for your inquiry. We are processing your request."
        if confirmed_items:
            intro += "\n\nWe have noted your interest in the following items:\n"
            for item in confirmed_items:
                intro += f"- {item}\n"

        return intro

    def _generate_questions(self, gaps: List[Dict[str, Any]]) -> str:
        """Generates up to two targeted questions or clarifications based on the identified gaps."""
        if not gaps:
            return ""

        questions = []

        # Priority 1: Handle ambiguous products.
        ambiguous_gap = next(
            (g for g in gaps if g["type"] == "AMBIGUOUS_PRODUCT"), None
        )
        if ambiguous_gap:
            question = (
                f"To ensure we quote the correct item, could you please clarify which product you meant for the request: "
                f"'{ambiguous_gap['details'].split('Best guess:')[0].split('Request')[-1].strip()}'? "
                f"Based on your request, we think you might mean: {ambiguous_gap['details'].split('Best guess:')[-1].strip()}."
            )
            questions.append(question)

        # Priority 2: Handle unknown products if there's still space.
        if len(questions) < 2:
            unknown_product_gap = next(
                (g for g in gaps if g["type"] == "UNKNOWN_PRODUCT"), None
            )
            if unknown_product_gap:
                # Extract product name from the details string, e.g., "Product 'XYZ' is not..."
                details = unknown_product_gap.get("details", "")
                match = re.search(r"'(.*?)'", details)
                product_name = match.group(1) if match else "the requested item"
                clarification = (
                    f"Please note that the item '{product_name}' is not available in our catalog. "
                    "We would be happy to help you find a suitable alternative."
                )
                questions.append(clarification)

        # Priority 3: Handle missing quantities if there's still space.
        if len(questions) < 2:
            missing_qty_gap = next(
                (g for g in gaps if g["type"] == "MISSING_QUANTITY"), None
            )
            if missing_qty_gap:
                product_name = missing_qty_gap["details"].split("'")[1]
                question = (
                    f"What quantity of the '{product_name}' would you like a quote for?"
                )
                questions.append(question)

        if not questions:
            return ""

        # Use a more generic intro since we might have clarifications, not just questions.
        return (
            "\n\nTo help us provide an accurate quote, we have a few points to clarify:\n\n"
            + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        )
