import os
import json
import time
import urllib.request
import urllib.error

def call_llm(system_prompt: str, user_prompt: str, max_retries: int = 5) -> str:
    """Calls an OpenAI-compatible chat completion endpoint using built-in urllib, with retry logic."""
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("LLM_MODEL", "llama-3.1-8b-instruct")

    url = f"{base_url.rstrip('/')}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    
    req_body = json.dumps(payload).encode("utf-8")
    
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            url,
            data=req_body,
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8")
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                # Wait 4s, 8s, 12s... for token bucket refill
                time.sleep(attempt * 4)
                continue
            raise RuntimeError(f"LLM API HTTP Error: {e.code} - {error_msg}")
        except Exception as e:
            if attempt < max_retries:
                time.sleep(attempt * 3)
                continue
            raise RuntimeError(f"Failed to communicate with LLM endpoint: {str(e)}")

    raise RuntimeError("Exceeded maximum retries for LLM API call.")

