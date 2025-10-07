import json
import abc
import os
from typing import Dict, Any
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if present


class LLMInterface(abc.ABC):
    """Abstract base class for LLM providers."""

    @abc.abstractmethod
    def get_structured_response(self, prompt: str) -> Dict[str, Any]:
        """Sends a prompt to the LLM and gets a structured JSON response."""
        pass


class OllamaInterface(LLMInterface):
    """LLM interface for a local Ollama server."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("ollama_settings", {})
        if not self.config:
            raise ValueError("Ollama settings are missing in the configuration.")

    def get_structured_response(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.config.get("model", "llama3:8b"),
            "format": "json",
            "prompt": prompt,
            "stream": False,
        }
        try:
            response = requests.post(
                self.config.get("base_url"),
                json=payload,
                timeout=self.config.get("timeout_seconds", 120),
            )
            response.raise_for_status()
            # The response from Ollama with format=json is a string that needs to be parsed again
            return json.loads(response.json().get("response"))
        except requests.RequestException as e:
            raise RuntimeError(
                f"Failed to connect to Ollama server at {self.config.get('base_url')}. Is Ollama running? Details: {e}"
            )
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse JSON from Ollama response. Details: {e}"
            )


class GeminiInterface(LLMInterface):
    """LLM interface for the Google Gemini API."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("gemini_settings", {})
        api_key = os.environ.get("GEMINI_API_KEY")

        if not self.config or not api_key:
            raise ValueError(
                "Gemini settings or API key are missing in config/llm_config.json."
            )

        if "YOUR_GEMINI_API_KEY_HERE" in api_key:
            raise ValueError(
                "Please replace 'YOUR_GEMINI_API_KEY_HERE' with your actual Gemini API key in config/llm_config.json."
            )

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.config.get("model", "gemini-2.5-flash"))

    def get_structured_response(self, prompt: str) -> Dict[str, Any]:
        try:
            # Use Gemini's JSON mode for reliable, clean JSON output.
            generation_config = {
                "response_mime_type": "application/json",
            }
            response = self.model.generate_content(
                prompt, generation_config=generation_config
            )

            # The response text should be a clean JSON string now.
            return json.loads(response.text)
        except Exception as e:
            # Provide a more informative error message.
            raise RuntimeError(
                f"Failed to call Gemini API. Check your API key and permissions. Details: {e}"
            )
