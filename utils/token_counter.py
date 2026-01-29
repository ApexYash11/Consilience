"""Utility to estimate/token-count LLM inputs and outputs (skeleton)."""


def count_tokens(text: str) -> int:
    """Very small token estimator; replace with real tokenizer for production."""
    # naive approximation: 1 token ~= 4 chars
    return max(1, len(text) // 4)


def estimate_call_cost(input_text: str, output_chars: int, pricing_per_million_input: float, pricing_per_million_output: float):
    input_tokens = count_tokens(input_text)
    output_tokens = max(1, output_chars // 4)
    cost = (input_tokens * pricing_per_million_input / 1_000_000) + (output_tokens * pricing_per_million_output / 1_000_000)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "estimated_cost": cost}
