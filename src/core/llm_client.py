# src/core/llm_client.py
"""LLM abstraction layer — Groq primary, Gemini fallback."""

import json
import traceback
from groq import Groq
import google.generativeai as genai
from config import (
    GROQ_API_KEY, GEMINI_API_KEY, GROQ_MODEL, GEMINI_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS
)


class GroqClient:
    """Wraps Groq SDK for Llama 3.3 70B chat completions."""

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

    def chat(self, messages: list, temperature: float = None, max_tokens: int = None) -> str:
        """Send messages and return assistant response text."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or LLM_TEMPERATURE,
                max_tokens=max_tokens or LLM_MAX_TOKENS,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")


class GeminiClient:
    """Wraps Google Generative AI SDK for Gemini chat."""

    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    def chat(self, messages: list, temperature: float = None, max_tokens: int = None) -> str:
        """Convert OpenAI-style messages to Gemini format and return response."""
        try:
            # Build Gemini-compatible history
            system_text = ""
            gemini_history = []

            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    system_text = content
                elif role == "user":
                    gemini_history.append({"role": "user", "parts": [content]})
                elif role == "assistant":
                    gemini_history.append({"role": "model", "parts": [content]})

            # Start chat with history (exclude last user message)
            chat = self.model.start_chat(history=gemini_history[:-1] if len(gemini_history) > 1 else [])

            # Prepend system prompt to last user message
            last_msg = gemini_history[-1]["parts"][0] if gemini_history else ""
            if system_text:
                last_msg = f"[System Instructions: {system_text}]\n\n{last_msg}"

            response = chat.send_message(
                last_msg,
                generation_config=genai.GenerationConfig(
                    temperature=temperature or LLM_TEMPERATURE,
                    max_output_tokens=max_tokens or LLM_MAX_TOKENS,
                ),
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")


class LLMRouter:
    """Routes to Groq first; falls back to Gemini on any failure."""

    def __init__(self):
        self.groq = GroqClient()
        self.gemini = GeminiClient()
        self._last_provider = None

    def chat(self, messages: list, temperature: float = None, max_tokens: int = None) -> str:
        """Try Groq → fallback Gemini. Returns response text."""
        # Try Groq first (faster, free tier usually sufficient)
        try:
            result = self.groq.chat(messages, temperature, max_tokens)
            self._last_provider = "groq"
            return result
        except Exception as groq_err:
            print(f"[LLMRouter] Groq failed: {groq_err}, falling back to Gemini...")
            traceback.print_exc()

        # Fallback to Gemini
        try:
            result = self.gemini.chat(messages, temperature, max_tokens)
            self._last_provider = "gemini"
            return result
        except Exception as gemini_err:
            print(f"[LLMRouter] Gemini also failed: {gemini_err}")
            traceback.print_exc()
            raise RuntimeError("Both Groq and Gemini APIs failed. Check your API keys.")

    @property
    def last_provider(self) -> str:
        return self._last_provider or "none"
