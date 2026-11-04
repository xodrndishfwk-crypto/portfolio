import json
import os
import time
import urllib.error
import urllib.request


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default

def _call_gemini(*, api_key: str, instructions: str, input_text: str, schema: dict, max_output_tokens: int = 500) -> dict | None:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        prompt = f"{instructions}\n\n[반환 형식]\n반드시 순수 JSON으로만 응답하세요.\n스키마: {json.dumps(schema, ensure_ascii=False)}"
        model = genai.GenerativeModel(model_name=model_name, generation_config={"response_mime_type": "application/json", "max_output_tokens": max_output_tokens, "temperature": 0.7})
        response = model.generate_content([prompt, input_text])
        if response and response.text:
            raw = response.text.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            elif raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            return json.loads(raw.strip())
    except Exception as e:
        print(f"[Gemini Error] {e}")
    return None


def _call_openai(*, api_key: str, instructions: str, input_text: str, schema_name: str, schema: dict, max_output_tokens: int = 500) -> dict | None:
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6"),
        "store": False,
        "instructions": instructions,
        "input": input_text,
        "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        "max_output_tokens": max_output_tokens,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    timeout = _positive_int_env("OPENAI_TIMEOUT_SECONDS", 30)
    attempts = _positive_int_env("OPENAI_MAX_ATTEMPTS", 2)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            output_text = result.get("output_text")
            if not output_text:
                choices = result.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    output_text = choices[0].get("message", {}).get("content", "")
            if not output_text:
                for item in result.get("output", []):
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_text = content.get("text")
                            break
            parsed = json.loads(output_text or "{}")
            return parsed if isinstance(parsed, dict) else None
        except urllib.error.HTTPError as error:
            retryable = error.code == 429 or error.code >= 500
            print(f"[OpenAI HTTP Error] status={error.code} attempt={attempt + 1}/{attempts}")
            if not retryable or attempt + 1 >= attempts:
                break
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"[OpenAI Network Error] attempt={attempt + 1}/{attempts}: {error}")
            if attempt + 1 >= attempts:
                break
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            print(f"[OpenAI Response Error] {error}")
            break
        if attempt + 1 < attempts:
            time.sleep(0.4 * (attempt + 1))
    return None


def request_structured_output(*, instructions: str, input_text: str, schema_name: str, schema: dict, max_output_tokens: int = 500) -> dict | None:
    provider = os.getenv("AI_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if provider == "gemini" and gemini_key:
        res = _call_gemini(api_key=gemini_key, instructions=instructions, input_text=input_text, schema=schema, max_output_tokens=max_output_tokens)
        if res:
            return {**res, "_provider": "gemini"}

    if openai_key:
        res = _call_openai(api_key=openai_key, instructions=instructions, input_text=input_text, schema_name=schema_name, schema=schema, max_output_tokens=max_output_tokens)
        if res:
            return {**res, "_provider": "openai"}

    if gemini_key and os.getenv("ENABLE_GEMINI_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}:
        res = _call_gemini(api_key=gemini_key, instructions=instructions, input_text=input_text, schema=schema, max_output_tokens=max_output_tokens)
        if res:
            return {**res, "_provider": "gemini"}

    return None
