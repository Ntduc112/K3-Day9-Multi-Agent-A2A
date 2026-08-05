import json
import os
from datetime import datetime

class TraceLogger:
    """Logs agent handoff events to trace.jsonl files."""
    
    def __init__(self, filepaths=None):
        if filepaths is None:
            self.filepaths = ["logging/trace.jsonl", "trace.jsonl"]
        else:
            self.filepaths = filepaths
            
        # Ensure parent directories exist and clear the files on startup
        for path in self.filepaths:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                pass  # Truncate/clear the file

    def log_handoff(self, case_id: str, from_agent: str, to_agent: str, status: str):
        """Records an agent handoff event with ISO timestamp."""
        # Use system local time with timezone offset
        timestamp = datetime.now().astimezone().isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "case_id": case_id,
            "event": "agent_handoff",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "status": status
        }
        
        for path in self.filepaths:
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except IOError:
                # Silently fail if one log file cannot be written to
                pass
