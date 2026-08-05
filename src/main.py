import os
import sys
import json
import argparse

# Increase Python's max string digits conversion limit for large JSON numbers
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(100000)

from src.trace import TraceLogger
from src.coordinator import Coordinator

def load_env():
    """Loads key-value pairs from a local .env file into os.environ."""
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                # Ignore inline comments
                if " #" in line or "\t#" in line:
                    line = line.split("#", 1)[0].strip()
                elif line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().strip('"').strip("'")
                    # Also strip inline comments from value if any remain
                    if " #" in val:
                        val = val.split("#", 1)[0].strip()
                    os.environ[key] = val


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Dispute Resolution End-to-End Runner")
    parser.add_argument("--input-dir", default="input", help="Directory containing input JSON files")
    parser.add_argument("--output-dir", default="output", help="Directory where output JSON files will be saved")
    parser.add_argument("--data-dir", default="data", help="Directory containing the Olist CSV dataset")
    parser.add_argument("--verify-dataset", action="store_true", default=True, help="Whether VerifierAgent should validate evidence against the CSV dataset")
    args = parser.parse_args()

    # 1. Load .env environment variables
    load_env()

    # 2. Initialize Logger (clears previous logs)
    logger = TraceLogger(filepaths=["logging/trace.jsonl", "trace.jsonl"])
    print("Trace logger initialized. Output will be written to logging/trace.jsonl and trace.jsonl.")

    # 3. Initialize Coordinator
    coordinator = Coordinator(data_dir=args.data_dir, verify_dataset=args.verify_dataset)
    print(f"Coordinator initialized with data directory: '{args.data_dir}'.")

    # 4. Scan and sort input cases
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        return

    input_files = sorted([
        f for f in os.listdir(args.input_dir)
        if f.startswith("EC_") and f.endswith(".json")
    ])

    if not input_files:
        print(f"No cases found in '{args.input_dir}'.")
        return

    print(f"Found {len(input_files)} cases to process.")
    os.makedirs(args.output_dir, exist_ok=True)

    # 5. Loop through cases
    for filename in input_files:
        input_path = os.path.join(args.input_dir, filename)
        output_path = os.path.join(args.output_dir, filename)
        
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                case_input = json.load(f)
            
            case_id = case_input.get("case_id", "Unknown")
            print(f"Processing case {case_id}...")
            
            # Execute workflow
            result = coordinator.run_case(case_input, logger)
            
            # Save output JSON
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Critical error processing file {filename}: {str(e)}")

    # 6. Write metadata.json
    model_name = os.environ.get("LLM_MODEL", "Llama-3-8B-Instruct")
    parameter_size = os.environ.get("LLM_PARAMETER_SIZE", "8B")
    framework = "Custom ReAct Supervisor Flow"
    runtime = os.environ.get("LLM_RUNTIME", "Local PC")

    metadata = {
        "model": model_name,
        "parameter_size": parameter_size,
        "framework": framework,
        "runtime": runtime
    }

    metadata_paths = ["logging/metadata.json", "metadata.json"]
    for path in metadata_paths:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"Metadata written to {path}.")
        except Exception as e:
            print(f"Failed to write metadata to {path}: {str(e)}")

    print("Workflow run completed successfully.")

if __name__ == "__main__":
    main()
