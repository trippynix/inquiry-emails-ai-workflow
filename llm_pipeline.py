import json
from pathlib import Path

# Assuming your modules are in a 'src' directory
from src.logging import log_activity
from src.quoting import QuoteGenerator
from src.llm_based.llm_inferencing import (
    get_llm_provider,
    create_llm_prompt,
    validate_llm_output,
)


def load_json_file(file_path: Path):
    """Loads a JSON file from the config directory."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # This is a critical error, so we print and return None
        print(f"CRITICAL ERROR: Could not load {file_path}. Reason: {e}")
        return None


def main():
    """Main function to orchestrate the LLM-powered AI workflow."""
    # --- 1. Setup Paths and Configuration ---
    project_root = Path(__file__).parent
    config_dir = project_root / "config"
    inbox_dir = project_root / "samples" / "inbox"
    data_dir = project_root / "data"
    events_dir = data_dir / "events"
    outbox_dir = data_dir / "outbox"
    quotes_dir = data_dir / "quotes"
    timeline_dir = data_dir / "timeline"

    # Create output directories if they don't exist
    for d in [events_dir, outbox_dir, quotes_dir, timeline_dir]:
        d.mkdir(parents=True, exist_ok=True)

    log_file = timeline_dir / "activity.jsonl"
    log_activity(log_file, "WORKFLOW_START", "INFO", "Workflow initiated.")

    # --- 2. Load Configs and Initialize Modules ---
    price_list = load_json_file(config_dir / "price_list.json")
    discount_rules = load_json_file(config_dir / "discount_rules.json")
    llm_config = load_json_file(config_dir / "llm_config.json")

    if not all([price_list, discount_rules, llm_config]):
        log_activity(
            log_file,
            "CONFIG_ERROR",
            "FAILURE",
            "Failed to load one or more config files. Aborting workflow.",
        )
        return

    try:
        llm_provider = get_llm_provider(llm_config)
        quote_generator = QuoteGenerator(price_list, discount_rules)
        log_activity(
            log_file,
            "SETUP",
            "SUCCESS",
            f"Modules initialized successfully using '{llm_config.get('provider')}' provider.",
        )
    except (ValueError, RuntimeError) as e:
        log_activity(
            log_file,
            "SETUP",
            "FAILURE",
            f"Failed to initialize LLM provider: {e}. Aborting workflow.",
        )
        return

    # --- 3. Main Email Processing Loop ---
    for email_file in inbox_dir.glob("*.txt"):
        # Use the file stem as the unique ID for simplicity and traceability
        email_id = email_file.stem

        try:
            # Idempotency Check: Skip if the final quote artifact already exists.
            quote_file = quotes_dir / f"{email_id}.json"
            if quote_file.exists():
                log_activity(
                    log_file,
                    "PROCESSING_SKIP",
                    "INFO",
                    f"Skipping {email_file.name}, quote already exists.",
                    {"email_id": email_id},
                )
                continue

            with open(email_file, "r", encoding="utf-8") as f:
                email_content = f.read()

            # --- Step 3a: LLM Inference ---
            llm_output = {}
            try:
                prompt = create_llm_prompt(email_content, price_list)
                log_activity(
                    log_file,
                    "LLM_INFERENCE_START",
                    "INFO",
                    "Sending prompt to LLM.",
                    {"email_id": email_id},
                )
                llm_output = llm_provider.get_structured_response(prompt)
                log_activity(
                    log_file,
                    "LLM_INFERENCE_SUCCESS",
                    "SUCCESS",
                    "Successfully received and parsed response from LLM.",
                    {"email_id": email_id},
                )
            except RuntimeError as e:
                # This catches connection errors from the interface and re-raises to the main error handler
                raise RuntimeError(f"LLM provider failed during API call: {e}")

            # --- Step 3b: Validation ---
            if not validate_llm_output(llm_output, price_list):
                # Raise an error to be caught by the except block
                raise RuntimeError(
                    "LLM output failed validation (schema mismatch or invalid product name)."
                )
            log_activity(
                log_file,
                "LLM_VALIDATION",
                "SUCCESS",
                "LLM output validated successfully.",
                {"email_id": email_id},
            )

            # --- Step 3c: Deterministic Execution & Saving Artifacts ---
            # 1. Save Parsed Event (Represents 'Email Parsing' completion)
            event_data = {
                "email_id": email_id,
                "sender": {
                    "name": llm_output.get("sender_name"),
                    "email": llm_output.get("sender_email"),
                },
                "subject": llm_output.get("subject"),
                "extracted_items": llm_output.get("extracted_items", []),
                "gaps_identified": llm_output.get("gaps_identified", []),
            }
            event_file = events_dir / f"{email_id}.json"
            with open(event_file, "w", encoding="utf-8") as f:
                json.dump(event_data, f, indent=2)
            log_activity(
                log_file,
                "PARSING_COMPLETE",
                "SUCCESS",
                "Parsed event data saved successfully.",
                {"email_id": email_id, "path": str(event_file)},
            )

            # 2. Save Acknowledgment Draft (Represents 'Acknowledgment Generation' completion)
            ack_draft = {
                "recipient_email": llm_output.get("sender_email"),
                "subject": f"Re: {llm_output.get('subject', 'Your Inquiry')}",
                "body": llm_output.get("drafted_acknowledgment_body"),
            }
            ack_file = outbox_dir / f"{email_id}_ack.json"
            with open(ack_file, "w", encoding="utf-8") as f:
                json.dump(ack_draft, f, indent=2)
            log_activity(
                log_file,
                "ACKNOWLEDGMENT_DRAFTED",
                "SUCCESS",
                "Acknowledgment draft saved successfully.",
                {"email_id": email_id, "path": str(ack_file)},
            )

            # 3. Generate and Save Quote (Represents 'Quoting' completion)
            quote_data = quote_generator.generate_quote(event_data)
            with open(quote_file, "w", encoding="utf-8") as f:
                json.dump(quote_data, f, indent=2)
            log_activity(
                log_file,
                "QUOTE_GENERATED",
                "SUCCESS",
                "Quote generated and saved successfully.",
                {"email_id": email_id, "path": str(quote_file)},
            )

        except Exception as e:
            # This block catches any failure during the processing of a single email
            log_activity(
                log_file,
                "PROCESSING_FAILURE",
                "FAILURE",
                f"Failed to process {email_file.name}.",
                {"email_id": email_id, "error": str(e)},
            )
            # The loop will continue to the next email

    log_activity(log_file, "WORKFLOW_END", "INFO", "Workflow finished.")


if __name__ == "__main__":
    main()
