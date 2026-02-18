import logging
from datetime import datetime

import openai

logger = logging.getLogger(__name__)
llm_debug_logger = logging.getLogger("config_generator.llm_debug")

OPENAI_PRICING = {
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
}


class LLMClient:
    """Thin wrapper around OpenAI chat completions with usage tracking and debug logging."""

    def __init__(self, api_key: str, model: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

    def call(self, prompt: str, step_label: str = "llm_call") -> str:
        """Call OpenAI API and return text response."""
        llm_debug_logger.debug(
            "\n========== LLM REQUEST [%s] ==========\n"
            "Timestamp: %s\n"
            "Model: %s\n"
            "Prompt length: %d chars\n\n"
            "--- PROMPT ---\n%s\n",
            step_label,
            datetime.now().isoformat(),
            self.model,
            len(prompt),
            prompt,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        input_tokens = 0
        output_tokens = 0
        cost = 0.0
        if response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            cost = self._calculate_cost(input_tokens, output_tokens)
            self.total_cost += cost

        response_text = response.choices[0].message.content

        llm_debug_logger.debug(
            "\n========== LLM RESPONSE [%s] ==========\n"
            "Timestamp: %s\n"
            "Tokens: input=%d, output=%d, cost=$%.4f\n\n"
            "--- RESPONSE ---\n%s\n",
            step_label,
            datetime.now().isoformat(),
            input_tokens,
            output_tokens,
            cost,
            response_text,
        )

        return response_text

    def get_usage_summary(self) -> dict:
        """Return cumulative usage stats."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 4),
        }

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD based on model pricing."""
        pricing = OPENAI_PRICING.get(self.model)
        if not pricing:
            return 0.0
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000
