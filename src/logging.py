import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import threading

# A lock to ensure that file writes are thread-safe.
log_lock = threading.Lock()

def log_activity(
    log_file_path: Path,
    event_type: str,
    status: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Constructs a log entry and appends it to the JSONL activity log file.

    Args:
        log_file_path: Path to the activity.jsonl file.
        event_type: A high-level category for the event (e.g., "EMAIL_PROCESSING").
        status: The outcome of the event ("SUCCESS", "FAILURE", "INFO").
        message: A human-readable description of the event.
        metadata: An optional dictionary for additional context (e.g., email_id, file_path).
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "status": status,
        "message": message,
        "metadata": metadata or {}
    }

    with log_lock:
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except IOError as e:
            print(f"Error: Could not write to log file {log_file_path}. Reason: {e}")
