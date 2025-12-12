import os
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
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
        

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(api_key or settings.OPENAI_API_KEY),
            temperature=temperature,
            )

# Example usage:
# llm = LLMFactory.create_llm(json_mode=False, tracing_project="course-generator")
# response = llm.invoke([HumanMessage(content="南海的西沙群岛和南沙群岛属于哪个国家？")])
# print(response.content)
# llama3.3-70b-instruct
# deepseek-ai/deepseek-v3.1-terminus
# qwen/qwen3-next-80b-a3b-instruct
# 
