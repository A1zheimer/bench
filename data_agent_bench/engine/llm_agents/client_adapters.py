import os
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel

class LLMResponse(BaseModel):
    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: float

class BaseLLMClient:
    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> LLMResponse:
        raise NotImplementedError

# Approximate per-token costs (USD)
_COST_TABLE = {
    "openai/gpt-4.1":           (2.00e-6, 8.00e-6),
    "openai/gpt-4.1-mini":      (0.40e-6, 1.60e-6),
    "openai/gpt-4.1-nano":      (0.10e-6, 0.40e-6),
    "openai/gpt-4o":            (2.50e-6, 10.00e-6),
    "openai/gpt-4o-mini":       (0.15e-6, 0.60e-6),
    "anthropic/claude-sonnet-4-6": (3.00e-6, 15.00e-6),
    "anthropic/claude-3-5-sonnet-20241022": (3.00e-6, 15.00e-6),
    "anthropic/claude-3-5-haiku-20241022": (0.80e-6, 4.00e-6),
    "deepseek/deepseek-chat":   (0.27e-6, 1.10e-6),
    "deepseek/deepseek-reasoner": (0.55e-6, 2.19e-6),
    "gemini/gemini-2.5-pro":    (1.25e-6, 10.00e-6),
    "gemini/gemini-2.5-flash":  (0.15e-6, 0.60e-6),
    "gemini/gemini-1.5-pro":    (1.25e-6, 5.00e-6),
    "gemini/gemini-1.5-flash":  (0.075e-6, 0.30e-6),
}

def calculate_cost(model_id: str, tokens_in: int, tokens_out: int) -> float:
    rate_in, rate_out = _COST_TABLE.get(model_id, (0.0, 0.0))
    return tokens_in * rate_in + tokens_out * rate_out

class OpenAIClient(BaseLLMClient):
    def __init__(self, model_id: str):
        import openai
        if model_id.startswith("deepseek/"):
            api_key = os.getenv("DEEPSEEK_API_KEY")
            base_url = "https://api.deepseek.com"
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
        self.full_model_id = model_id

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature
        )
        text = response.choices[0].message.content or ""
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0
        cost = calculate_cost(self.full_model_id, tokens_in, tokens_out)
        return LLMResponse(text=text, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost)

class AnthropicClient(BaseLLMClient):
    def __init__(self, model_id: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
        self.full_model_id = model_id

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> LLMResponse:
        # Convert messages to Anthropic format (system prompt needs to be separated)
        system_prompt = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt += msg["content"] + "\n"
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})
        
        response = self.client.messages.create(
            model=self.model_name,
            system=system_prompt.strip() if system_prompt else anthropic.NOT_GIVEN,
            messages=anthropic_messages,
            temperature=temperature,
            max_tokens=4096
        )
        text = response.content[0].text if response.content else ""
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        cost = calculate_cost(self.full_model_id, tokens_in, tokens_out)
        return LLMResponse(text=text, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost)

class GeminiClient(BaseLLMClient):
    def __init__(self, model_id: str):
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        self.model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
        self.full_model_id = model_id
        self.client = genai.GenerativeModel(self.model_name)

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> LLMResponse:
        # Convert messages to Gemini format
        system_instruction = ""
        gemini_history = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction += msg["content"] + "\n"
            else:
                # Gemini roles: user, model
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})
        
        # We use a fresh model instance with system instruction if present
        import google.generativeai as genai
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction.strip() if system_instruction else None
        )
        
        response = model.generate_content(
            gemini_history,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
            )
        )
        
        text = response.text
        usage = response.usage_metadata
        tokens_in = usage.prompt_token_count
        tokens_out = usage.candidates_token_count
        cost = calculate_cost(self.full_model_id, tokens_in, tokens_out)
        return LLMResponse(text=text, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost)

def get_llm_client(model_id: str) -> BaseLLMClient:
    """Factory to get the correct LLM client."""
    if model_id.startswith("openai/"):
        return OpenAIClient(model_id)
    elif model_id.startswith("anthropic/"):
        return AnthropicClient(model_id)
    elif model_id.startswith("gemini/"):
        return GeminiClient(model_id)
    elif model_id.startswith("deepseek/"):
        return OpenAIClient(model_id)
    elif model_id.startswith("vllm/"):
        return OpenAIClient(model_id)
    else:
        raise ValueError(f"Unsupported model provider in model_id: {model_id}. Use openai/, anthropic/, gemini/, deepseek/, or vllm/")
