"""
OpenAI LLM Service implementation.

Uses OpenAI API for tool calling and reasoning.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import json

from openai import AsyncOpenAI

from .llm_service import LLMService, LLMProvider


logger = logging.getLogger(__name__)


class OpenAIService(LLMService):
    """
    OpenAI implementation of LLMService.

    Supports:
    - gpt-4o-mini: Fast, cheap tool calling
    - o3-mini: Reasoning model (more expensive)
    """

    def __init__(
        self,
        tool_calling_model: str = "gpt-4o-mini",
        reasoning_model: str = "gpt-4o-mini",  # o3-mini can be expensive
        api_key: Optional[str] = None
    ):
        """
        Initialize OpenAI service.

        Args:
            tool_calling_model: Model for tool calling (default: gpt-4o-mini)
            reasoning_model: Model for reasoning (default: gpt-4o-mini, can use o3-mini)
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.tool_calling_model = tool_calling_model
        self.reasoning_model = reasoning_model

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY not set")

        self.client = AsyncOpenAI(api_key=api_key)

        logger.info(
            f"OpenAI service initialized: tool_calling={tool_calling_model}, "
            f"reasoning={reasoning_model}"
        )

    async def call_tool(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Call OpenAI with function calling.

        Args:
            prompt: User prompt
            tools: Tool definitions (OpenAI format)
            temperature: Sampling temperature

        Returns:
            Dict with parsed tool call arguments
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.tool_calling_model,
                messages=[{"role": "user", "content": prompt}],
                tools=[{"type": "function", "function": tool} for tool in tools],
                tool_choice="auto",
                temperature=temperature,
            )

            # Extract tool call
            message = response.choices[0].message

            if not message.tool_calls:
                # No tool called, return empty
                logger.warning(f"No tool called for prompt: {prompt}")
                return {}

            tool_call = message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)

            logger.debug(f"Tool call successful: {tool_call.function.name}, args={arguments}")

            return {
                "function_name": tool_call.function.name,
                "arguments": arguments
            }

        except Exception as e:
            logger.error(f"OpenAI tool call error: {e}", exc_info=True)
            raise

    async def reason(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Call OpenAI for reasoning.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.reasoning_model,
                messages=messages,
                temperature=temperature,
            )

            result = response.choices[0].message.content

            logger.debug(f"Reasoning complete: {len(result)} chars")

            return result

        except Exception as e:
            logger.error(f"OpenAI reasoning error: {e}", exc_info=True)
            raise

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI

    @property
    def model_name(self) -> str:
        return f"{self.tool_calling_model} (tools), {self.reasoning_model} (reasoning)"
