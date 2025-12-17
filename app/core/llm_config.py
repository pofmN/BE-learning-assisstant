import os
from typing import Optional
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from app.core.config import settings

class LLMFactory:
    """Factory for creating configured LLM instances with tracing."""

    @staticmethod
    def create_llm(
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = "",
        temperature: float = 0.7,
        json_mode: bool = True,
        tracing_project: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> ChatOpenAI:
        """
        Create a configured ChatOpenAI instance.
        
        Args:
            model: The model name to use.
            temperature: The temperature for generation.
            json_mode: Whether to enforce JSON output.
            tracing_project: The LangSmith project name for tracing.
            api_key: OpenAI API key (optional, defaults to settings).
        """
        # Set env vars for tracing if provided
        if settings.LANGSMITH_TRACING and str(settings.LANGSMITH_TRACING).lower() == "true":
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
            os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = tracing_project or settings.LANGSMITH_PROJECT

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key or settings.OPENAI_API_KEY),
            temperature=temperature,
            # If ChatOpenAI supports tracing params, add them here
        )
