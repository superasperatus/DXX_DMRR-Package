"""Editable provider settings and the schema for newly collected responses."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = "You are answering a question. You must choose exactly one of three options."

# Add your own chat-completions endpoints, including API versions if required.
# To add a model, copy an entry and adjust its ID, authentication, and parameters.
# Set the named environment variable yourself; never paste credentials here.
MODELS = {
    "gpt-4.1": {
        "endpoint": "", "key_env": "AZURE_OPENAI_API_KEY", "auth": "api-key",
        "parameters": {
            "model": "gpt-4.1", "max_completion_tokens": 20,
            "top_p": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0,
        },
    },
    "gpt-4.1-mini": {
        "endpoint": "", "key_env": "AZURE_OPENAI_API_KEY", "auth": "api-key",
        "parameters": {
            "model": "gpt-4.1-mini", "max_completion_tokens": 20,
            "top_p": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0,
        },
    },
    "gpt-4o": {
        "endpoint": "", "key_env": "AZURE_OPENAI_API_KEY", "auth": "api-key",
        "parameters": {"model": "gpt-4o", "max_tokens": 20, "top_p": 1.0},
    },
    "o4-mini": {
        "endpoint": "", "key_env": "AZURE_OPENAI_API_KEY", "auth": "api-key",
        "parameters": {"model": "o4-mini", "max_completion_tokens": 2048},
    },
    "Llama-3.3-70B-Instruct": {
        "endpoint": "", "key_env": "AZURE_OPENAI_API_KEY", "auth": "bearer",
        "parameters": {"model": "Llama-3.3-70B-Instruct", "max_tokens": 20},
    },
    "Phi-4": {
        "endpoint": "", "key_env": "AZURE_OPENAI_API_KEY", "auth": "bearer",
        "parameters": {"model": "Phi-4", "max_tokens": 20},
    },
}

# Add models here when their provider does not support requested temperatures.
FIXED_TEMPERATURE_MODELS = {"o4-mini"}
FIELDS = [
    "item_id", "model_id", "condition", "trial_no", "raw_response",
    "parsed_response", "prompt_tokens", "completion_tokens", "latency_s",
    "timestamp", "error", "response_coding", "requested_temperature",
    "provider_model", "provider_response_id", "system_fingerprint", "finish_reason",
]


def parameters_for(model: str, temperature: float) -> dict:
    # Copy settings so adding a temperature never mutates the editable defaults.
    parameters = dict(MODELS[model]["parameters"])
    if model not in FIXED_TEMPERATURE_MODELS:
        parameters["temperature"] = temperature
    return parameters
