"""Provider-switchable chat client (OpenAI-compatible).
  LLM_PROVIDER=zai  -> Z.ai GLM, for quality/iteration testing (default)
  LLM_PROVIDER=near -> near.ai GLM, confidential TEE inference, for deployment testing
Never route chat to a Claude/Sonnet model on near (expensive). near = whisper + GLM only.
"""
import os, time, httpx

PROVIDERS = {
    "zai":  {"base": "https://api.z.ai/api/coding/paas/v4", "key": "ZAI_API_KEY",  "model": "glm-4.6"},
    "near": {"base": "https://cloud-api.near.ai/v1",  "key": "NEAR_API_KEY", "model": "zai-org/GLM-5.1-FP8"},
}
ENV = os.path.join(os.path.dirname(__file__), "..", ".env")


def _env(name):
    if os.environ.get(name):
        return os.environ[name]
    for line in open(ENV):
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{name} not set (env or .env)")


def provider():
    return os.environ.get("LLM_PROVIDER", "zai")


def default_model():
    return PROVIDERS[provider()]["model"]


def chat(messages, model=None, max_tokens=2048, json_mode=False, timeout=300, temperature=None,
         think=True):
    cfg = PROVIDERS[provider()]
    body = {"model": model or cfg["model"], "max_tokens": max_tokens, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if not think:
        body["thinking"] = {"type": "disabled"}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    url = f"{cfg['base']}/chat/completions"
    headers = {"Authorization": f"Bearer {_env(cfg['key'])}"}
    for i in range(8):  # congestion is transient -> back off persistently rather than throttle
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError):
            if i == 7:
                raise
            time.sleep(min(2 ** i, 30))
            continue
        if r.status_code == 429:
            time.sleep(min(2 ** i, 30))
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    r.raise_for_status()
