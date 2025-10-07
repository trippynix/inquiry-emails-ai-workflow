import json
import os
from pathlib import Path

# Import our custom modules from the 'src' directory
from src.lightweight_offline.email_parser import EmailParser, generate_email_id
from src.logging import log_activity
from src.lightweight_offline.acknowledgment import AcknowledgmentGenerator
from src.quoting import QuoteGenerator


def load_json_file(file_path: Path):
    """Loads a JSON file from the config directory."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # This is a critical error, so we print it and it will be logged by the caller
        print(f"Critical Error: Could not load {file_path}. Reason: {e}")
        return None


def main():
    """Main function to orchestrate the AI workflow."""
    print("Starting the AI workflow...")
    # --- 1. Setup Paths and Configuration ---
    print("Setting up directories and loading configuration...")
    project_root = Path(__file__).parent
    config_dir = project_root / "config"
    inbox_dir = project_root / "samples" / "inbox"
    data_dir = project_root / "data"
    events_dir = data_dir / "events"
    outbox_dir = data_dir / "outbox"
    quotes_dir = data_dir / "quotes"
    timeline_dir = data_dir / "timeline"

    # Create output directories if they don't exist
    events_dir.mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    quotes_dir.mkdir(parents=True, exist_ok=True)
    timeline_dir.mkdir(parents=True, exist_ok=True)

    log_file = timeline_dir / "activity.jsonl"

    # --- 2. Load Resources ---
    print("Loading configuration files...")
    log_activity(log_file, "WORKFLOW_START", "INFO", "Workflow initiated.")

    price_list = load_json_file(config_dir / "price_list.json")
    discount_rules = load_json_file(config_dir / "discount_rules.json")

    if not price_list or not discount_rules:
        log_activity(
            log_file,
            "CONFIG_ERROR",
            "FAILURE",
            "Failed to load price_list.json or discount_rules.json. Aborting workflow.",
        )
        return

    print("Configuration files loaded successfully.")
    print("Initializing modules...")
    # Initialize modules
    parser = EmailParser(price_list)
    ack_generator = AcknowledgmentGenerator()
    quote_generator = QuoteGenerator(price_list, discount_rules)
    log_activity(
        log_file, "SETUP", "SUCCESS", "Configuration loaded and modules initialized."
    )

    # --- 3. Parsing Stage ---
    print("Starting email parsing stage...")
    log_activity(
        log_file, "EMAIL_PROCESSING_START", "INFO", "Starting email parsing stage."
    )
    for email_file in inbox_dir.glob("*.txt"):
        # print("ASDASDASDASD", os.path.basename(email_file).split(".")[0])
        try:
            with open(email_file, "r", encoding="utf-8") as f:
                content = f.read()

            email_id = generate_email_id(content)
            output_file = events_dir / f"{email_id}.json"

            if output_file.exists():
                log_activity(
                    log_file,
                    "EMAIL_PROCESSING_SKIP",
                    "INFO",
                    f"Skipping {email_file.name}, event file already exists.",
                    {"email_id": email_id},
                )
                continue

            parsed_data = parser.parse_email(content)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, indent=2)

            log_activity(
                log_file,
                "EMAIL_PARSE",
                "SUCCESS",
                f"Successfully parsed {email_file.name}.",
                {"email_id": email_id, "output_path": str(output_file)},
            )

        except Exception as e:
            log_activity(
                log_file,
                "EMAIL_PARSE",
                "FAILURE",
                f"Failed to process {email_file.name}.",
                {"error": str(e), "file_path": str(email_file)},
            )
    log_activity(
        log_file, "EMAIL_PROCESSING_END", "INFO", "Email parsing stage finished."
    )
    print("Email parsing stage completed.")

    # --- 4. Acknowledgment Stage ---
    print("Starting acknowledgment generation stage...")
    log_activity(
        log_file,
        "ACK_GENERATION_START",
        "INFO",
        "Starting acknowledgment generation stage.",
    )
    for event_file in events_dir.glob("*.json"):
        try:
            email_id = event_file.stem
            ack_file_path = outbox_dir / f"{email_id}_ack.json"

            if ack_file_path.exists():
                log_activity(
                    log_file,
                    "ACK_GENERATION_SKIP",
                    "INFO",
                    f"Skipping acknowledgment for {email_id}, file already exists.",
                    {"event_file": str(event_file)},
                )
                continue

            with open(event_file, "r", encoding="utf-8") as f:
                parsed_event_data = json.load(f)

            ack_draft = ack_generator.generate_acknowledgment(parsed_event_data)

            with open(ack_file_path, "w", encoding="utf-8") as f:
                json.dump(ack_draft, f, indent=2)

            log_activity(
                log_file,
                "ACK_DRAFT_CREATE",
                "SUCCESS",
                f"Created acknowledgment draft for {email_id}.",
                {"output_path": str(ack_file_path)},
            )

        except Exception as e:
            log_activity(
                log_file,
                "ACK_DRAFT_CREATE",
                "FAILURE",
                f"Failed to generate acknowledgment for event {event_file.name}.",
                {"error": str(e)},
            )
    log_activity(
        log_file,
        "ACK_GENERATION_END",
        "INFO",
        "Acknowledgment generation stage finished.",
    )
    print("Acknowledgment generation stage completed.")

    # --- 5. Quoting Stage ---
    print("Starting quote generation stage...")
    log_activity(
        log_file, "QUOTE_GENERATION_START", "INFO", "Starting quote generation stage."
    )
    for event_file in events_dir.glob("*.json"):
        try:
            email_id = event_file.stem
            quote_file_path = quotes_dir / f"{email_id}.json"

            if quote_file_path.exists():
                log_activity(
                    log_file,
                    "QUOTE_GENERATION_SKIP",
                    "INFO",
                    f"Skipping quote for {email_id}, file already exists.",
                )
                continue

            with open(event_file, "r", encoding="utf-8") as f:
                parsed_event_data = json.load(f)

            quote_data = quote_generator.generate_quote(parsed_event_data)

            with open(quote_file_path, "w", encoding="utf-8") as f:
                json.dump(quote_data, f, indent=2)

            log_activity(
                log_file,
                "QUOTE_CREATE",
                "SUCCESS",
                f"Created quote for {email_id}. Status: {quote_data['status']}.",
                {"output_path": str(quote_file_path)},
            )

        except Exception as e:
            log_activity(
                log_file,
                "QUOTE_CREATE",
                "FAILURE",
                f"Failed to generate quote for event {event_file.name}.",
                {"error": str(e)},
            )
    log_activity(
        log_file, "QUOTE_GENERATION_END", "INFO", "Quote generation stage finished."
    )
    print("Quote generation stage completed.")
    # --- 6. Finalization ---
    log_activity(log_file, "WORKFLOW_END", "INFO", "Workflow finished.")
    print("Workflow completed.")


if __name__ == "__main__":
    main()
