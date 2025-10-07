## AI Workflow for Processing Inquiry Emails

This project implements a deterministic AI workflow that ingests inquiry emails, extracts structured data, drafts an acknowledgment, and generates a price quote as a JSON artifact. The system is designed to operate offline, persist artifacts to the filesystem, and handle varied email structures gracefully.

The project provides two distinct pipelines for processing:

1. LLM-Based Pipeline (llm_pipeline.py): A powerful, modern approach using a Large Language Model (either local via Ollama or API-based via Gemini) for high-accuracy semantic parsing and response generation.

2. Lightweight Offline Pipeline (fuzzyparsing_pipeline.py): A minimal-dependency, fully offline workflow that uses fuzzy string matching to parse emails. It is faster and requires no special hardware or API keys.

## Features

- Dual-Pipeline Architecture: Choose between a high-accuracy LLM pipeline or a lightweight, fully offline fuzzy-parsing pipeline.

- Structured Data Extraction: Parses emails to extract sender details, products, and quantities.

- Automated Acknowledgment: Generates professional acknowledgment drafts that confirm requests and ask clarifying questions to resolve gaps.

- Deterministic Quoting: Applies pricing, tiered bulk discounts, and category-based discounts to generate accurate quotes.

- Idempotent & Resilient: The workflow will not re-process emails and will log failures without crashing.

- Comprehensive Logging: An append-only activity log (activity.jsonl) captures every step of the workflow for full traceability.

## How to Run the Workflow

### 1. Setup

- Clone the repository and install dependencies:

  ```bash
  git clone https://github.com/trippynix/inquiry-emails-ai-workflow
  cd inquiry-emails-ai-workflow
  pip install -r requirements.txt
  ```

- Configure the workflow:

  All configuration is done in the `config/` directory.

  - `price_list.json`: Add or modify products, prices, and categories.

  - `discount_rules.json`: Adjust bulk/category discount tiers and the tax rate.

### 2. Running the LLM-Based Pipeline

This pipeline offers the highest accuracy.

- Configure the LLM Provider:

  Edit `config/llm_config.json` to choose your provider.

  - For Local LLM (Ollama):

    - Ensure Ollama is running on your machine.

    - Set the "provider" to "ollama".

    ```json
    {
      "provider": "ollama",
      "ollama_settings": {
        "base_url": "http://localhost:11434/api/generate",
        "model": "llama3:8b"
      }
      // ...
    }
    ```

  - For Google Gemini API:

    - Get your API key from Google AI Studio.

    - Create a .env file in the project root and add your key: GEMINI_API_KEY=your_actual_api_key_here

    - Set the "provider" to "gemini".

    ```json
    {
      "provider": "gemini",
      "gemini_settings": {
        "model": "gemini-2.5-flash"
      }
    }
    ```

- Execute the script:
  ```bash
  python llm_pipeline.py
  ```

### 3. Running the Lightweight Offline Pipeline

This pipeline is fast, has no external dependencies, and works completely offline.

- Execute the script:
  ```bash
  python fuzzyparsing_pipeline.py
  ```

## Schema Definitions

Parsed Event (`data/events/`)

Describes the information extracted from an email.

```json
{
  "email_id": "string",
  "sender": { "name": "string | null", "email": "string" },
  "subject": "string",
  "extracted_items": [
    {
      "product_name": "string | null",
      "mentioned_as": "string",
      "quantity": "integer | null",
      "confidence": {
        "product": "float",
        "quantity": "float"
      }
    }
  ],
  "gaps_identified": [
    {
      "type": "string (MISSING_QUANTITY, AMBIGUOUS_PRODUCT, UNKNOWN_PRODUCT)",
      "details": "string"
    }
  ]
}
```

Quote (`data/quotes/`)

Contains the final pricing information. If `status` is `"pending"`, the quote could not be calculated due to gaps.

```json
{
  "quote_id": "string",
  "status": "string (success or pending)",
  "line_items": [
    {
      "product_name": "string",
      "quantity": "integer",
      "unit_price": "float",
      "subtotal": "float",
      "total_discount_applied": "float",
      "final_price": "float"
    }
  ],
  "summary": {
    "grand_subtotal": "float",
    "total_discount": "float",
    "net_total_before_tax": "float",
    "tax_amount": "float",
    "grand_total": "float"
  }
}
```

## Assumptions and Known Limitations

- **Email Format**: The system assumes emails are in plain text (.txt) format.

- **Single Source of Truth**: Product matching is strictly limited to the items listed in `config/price_list.json`. The system will not recognize or quote products that are not in this catalog.

- **Single Currency**: The workflow assumes a single, implicit currency defined by the `price_list.json`. It does not handle multi-currency requests.

- **Deterministic Logic**: The quoting module is fully deterministic. All calculations (discounts, tax) are applied in a fixed order for consistency.

- **LLM Reliability**: The LLM-based pipeline's accuracy is dependent on the chosen model. The system includes a validation layer to ensure the LLM's output conforms to the required schema and does not "hallucinate" products.

- **Lightweight Model Accuracy**: The fuzzy-parsing pipeline relies on Levenshtein distance for product matching. This can sometimes lead to false positives where lexically similar but semantically different words get a high score (e.g., "hello" might be matched with "Dell Laptop").

## Example Outputs

### Example 1: Complete Pass (email_02.txt)

The workflow successfully parses all items and generates a complete quote.

- `data/events/email_02.json` (Parsed Event)

```json
{
  "email_id": "email_02",
  "sender": {
    "name": "Rajiv",
    "email": "rajiv.mehta@solutions.co.in"
  },
  "subject": "Office IT Equipment Order",
  "extracted_items": [
    {
      "product_name": "Wireless Mouse",
      "mentioned_as": "Wireless Mouse",
      "quantity": 15,
      "confidence": {
        "product": 1.0,
        "quantity": 1.0
      }
    },
    {
      "product_name": "Mechanical Keyboard",
      "mentioned_as": "Mechanical Keyboard",
      "quantity": 15,
      "confidence": {
        "product": 1.0,
        "quantity": 1.0
      }
    },
    {
      "product_name": "HP EliteBook 840",
      "mentioned_as": "HP EliteBook 840",
      "quantity": 5,
      "confidence": {
        "product": 1.0,
        "quantity": 1.0
      }
    },
    {
      "product_name": "Laser Printer",
      "mentioned_as": "Laser Printer",
      "quantity": 2,
      "confidence": {
        "product": 1.0,
        "quantity": 1.0
      }
    }
  ],
  "gaps_identified": []
}
```

- `data/quotes/email_02.json` (Generated Quote)

```json
{
  "quote_id": "email_02",
  "status": "success",
  "line_items": [
    {
      "product_name": "Wireless Mouse",
      "quantity": 15,
      "unit_price": 800,
      "subtotal": 12000,
      "total_discount_applied": 1740.0,
      "final_price": 10260.0
    },
    {
      "product_name": "Mechanical Keyboard",
      "quantity": 15,
      "unit_price": 3500,
      "subtotal": 52500,
      "total_discount_applied": 7612.5,
      "final_price": 44887.5
    },
    {
      "product_name": "HP EliteBook 840",
      "quantity": 5,
      "unit_price": 65000,
      "subtotal": 325000,
      "total_discount_applied": 25512.5,
      "final_price": 299487.5
    },
    {
      "product_name": "Laser Printer",
      "quantity": 2,
      "unit_price": 18000,
      "subtotal": 36000,
      "total_discount_applied": 360.0,
      "final_price": 35640.0
    }
  ],
  "summary": {
    "grand_subtotal": 425500,
    "total_discount": 35225.0,
    "net_total_before_tax": 390275.0,
    "tax_amount": 70249.5,
    "grand_total": 460524.5
  }
}
```

### Example 2: Pending-Quote Pass (email_03.txt)

The workflow identifies an ambiguous product request and marks the quote as pending. The acknowledgment draft will contain a question to resolve this gap.

- `data/events/email_03.json` (Parsed Event)

```json
{
  "email_id": "email_03",
  "sender": {
    "name": "Priya Singh",
    "email": "contact@startupfoundry.io"
  },
  "subject": "Laptop inquiry",
  "extracted_items": [
    {
      "product_name": null,
      "mentioned_as": "a ThinkPad model",
      "quantity": 4,
      "confidence": {
        "product": 0.0,
        "quantity": 1.0
      }
    }
  ],
  "gaps_identified": [
    {
      "type": "AMBIGUOUS_PRODUCT",
      "details": "The customer expressed interest in 'a ThinkPad model', but our catalog lists 'Lenovo ThinkPad E14' and 'Lenovo ThinkPad L14'. Please clarify which specific model is preferred."
    }
  ]
}
```

- `data/quotes/email_03.json` (Pending Quote)

```json
{
  "quote_id": "email_03",
  "status": "pending",
  "pending_reason": "One or more items could not be identified or are missing quantities.",
  "gaps": [
    {
      "type": "AMBIGUOUS_PRODUCT",
      "details": "The customer expressed interest in 'a ThinkPad model', but our catalog lists 'Lenovo ThinkPad E14' and 'Lenovo ThinkPad L14'. Please clarify which specific model is preferred."
    }
  ],
  "line_items": [],
  "summary": {}
}
```
