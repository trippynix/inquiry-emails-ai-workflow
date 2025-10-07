import json
from typing import Dict, Any

from src.llm_based.llm_interface import GeminiInterface, LLMInterface, OllamaInterface


def get_llm_provider(config: Dict[str, Any]) -> LLMInterface:
    """Factory function to get the configured LLM provider."""
    provider = config.get("provider", "").lower()
    if provider == "ollama":
        return OllamaInterface(config)
    elif provider == "gemini":
        return GeminiInterface(config)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. Choose 'ollama' or 'gemini'."
        )


def create_llm_prompt(email_content: str, price_list: Dict[str, Any]) -> str:
    """Creates the detailed, one-shot prompt for the LLM."""

    # Prune price list to only include essential info for the LLM
    product_catalog = {
        name: {"category": details["category"]} for name, details in price_list.items()
    }

    schema = {
        "sender_name": "string | null",
        "sender_email": "string",
        "subject": "string",
        "extracted_items": [
            {
                "product_name": "string | null (must be an exact key from the catalog)",
                "mentioned_as": "string (what the user actually wrote)",
                "quantity": "integer | null",
                "confidence": {
                    "product": "float (0.0 to 1.0, where 1.0 is certain)",
                    "quantity": "float (0.0 to 1.0, where 1.0 is certain)",
                },
            }
        ],
        "gaps_identified": [
            {
                "type": "string (MISSING_QUANTITY, AMBIGUOUS_PRODUCT, or UNKNOWN_PRODUCT)",
                "details": "string (a clear, user-facing explanation of the gap)",
            }
        ],
        "drafted_acknowledgment_body": "string (the full, polite, ready-to-use body of the acknowledgment email, asking questions if gaps exist)",
    }

    prompt = f"""
    You are an expert sales assistant for Kreeda Labs. Your task is to analyze a customer inquiry email and extract all relevant information into a structured JSON format.
    READ VERY CAREFULLY THE GIVEN EMAIL CONTENT AND THE INSTRUCTIONS BELOW.

    You MUST use the provided product catalog as your single source of truth. Do not invent products.
    - STRICTLY adhere to the schema
    - Be sure to fill in all fields, using null where appropriate and especially gaps identified field if any issues are found
    - If a user mentions a product with a typo, match it to the closest item in the catalog.
    - If a user asks for a product not in the catalog, you must identify it as an "UNKNOWN_PRODUCT".
    - If a user does not specify quantity for a mentioned product, identify it as "MISSING_QUANTITY".
    - If a user mentions a category like "a ThinkPad" and there are multiple options, identify it as "AMBIGUOUS_PRODUCT".
    - Extract the sender's name from the signature if available.
    - For each item, provide a confidence score (0.0 to 1.0) for both the product match and the quantity. A score of 1.0 means you are certain.
    - Draft a professional and helpful acknowledgment email body. If you identify any gaps, your draft must include targeted questions to resolve them.

    HERE IS THE OFFICIAL PRODUCT CATALOG:
    {json.dumps(product_catalog, indent=2)}

    Analyze the following email and respond ONLY with a single, valid JSON object that conforms to the schema below. Do not add any text, explanation, or markdown formatting before or after the JSON.

    EMAIL TO ANALYZE:
    ---
    {email_content}
    ---

    JSON SCHEMA TO FOLLOW:
    {json.dumps(schema, indent=2)}
    """
    return prompt


def validate_llm_output(llm_json: Dict[str, Any], price_list: Dict[str, Any]) -> bool:
    """Validates the structure and content of the LLM's JSON output."""
    required_keys = [
        "sender_email",
        "extracted_items",
        "gaps_identified",
        "drafted_acknowledgment_body",
    ]
    for key in required_keys:
        if key not in llm_json:
            return False

    for item in llm_json.get("extracted_items", []):
        product_name = item.get("product_name")
        if product_name and product_name not in price_list:
            # The LLM hallucinated a product that's not in our list
            return False

    return True
