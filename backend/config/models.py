"""
Model selection and configuration for Consilience.

Defines models for Standard Research (free tier) and Deep Research (paid tier).
All models are sourced from OpenRouter for easy switching and cost tracking.
"""

from enum import Enum
from typing import Dict, Literal
import os


class ResearchMode(str, Enum):
    """Research tier selection."""
    STANDARD = "standard"
    DEEP = "deep"


class ModelPhase(str, Enum):
    """Research workflow phases."""
    PLANNING = "planning"
    RESEARCH = "research"
    VERIFICATION = "verification"
    DETECTION = "detection"
    SYNTHESIS = "synthesis"
    REVIEW = "review"
    REVISION = "revision"
    FORMATTING = "formatting"


# MODEL SELECTION


STANDARD_MODELS: Dict[str, str] = {
    # Free models for Standard Research tier - cost $0.00 per paper
    ModelPhase.PLANNING.value: "deepseek/deepseek-r1-0528:free",
    # Best for reasoning and planning; matches OpenAI o1 performance
    
    ModelPhase.RESEARCH.value: "qwen/qwen-2.5-7b-instruct:free",
    # Fast parallel execution; strong multilingual support
    
    ModelPhase.VERIFICATION.value: "deepseek/deepseek-r1-distill-qwen-7b:free",
    # Strong reasoning for credibility assessment
    
    ModelPhase.DETECTION.value: "meta-llama/llama-3.3-70b-instruct:free",
    # Excellent at comparative reasoning for contradiction detection
    
    ModelPhase.SYNTHESIS.value: "deepseek/deepseek-r1-0528:free",
    # Best free model for long-form writing
    
    ModelPhase.REVIEW.value: "google/gemma-3-27b:free",
    # Strong instruction following for peer review and critique
    
    ModelPhase.REVISION.value: "deepseek/deepseek-r1-0528:free",
    # Good at iterative improvement
    
    ModelPhase.FORMATTING.value: "qwen/qwen-2.5-coder-7b-instruct:free",
    # Specialized for code/structured output (citations)
}

DEEP_MODELS: Dict[str, str] = {
    # Kimi K2.5 for Deep Research tier - cost $0.25-0.50 per paper
    # Uses single model for all phases - native multimodal, agent swarm, tool use
    ModelPhase.PLANNING.value: "moonshotai/kimi-k2.5",
    ModelPhase.RESEARCH.value: "moonshotai/kimi-k2.5",
    ModelPhase.VERIFICATION.value: "moonshotai/kimi-k2.5",
    ModelPhase.DETECTION.value: "moonshotai/kimi-k2.5",
    ModelPhase.SYNTHESIS.value: "moonshotai/kimi-k2.5",
    ModelPhase.REVIEW.value: "moonshotai/kimi-k2.5",
    ModelPhase.REVISION.value: "moonshotai/kimi-k2.5",
    ModelPhase.FORMATTING.value: "moonshotai/kimi-k2.5",
}

# Alternative for budget-constrained deep research
DEEPSEEK_V3_MODELS: Dict[str, str] = {
    # DeepSeek V3.2 for cost-optimized deep research - cost $0.15-0.25 per paper
    ModelPhase.PLANNING.value: "deepseek/deepseek-v3.2",
    ModelPhase.RESEARCH.value: "deepseek/deepseek-v3.2",
    ModelPhase.VERIFICATION.value: "deepseek/deepseek-v3.2",
    ModelPhase.DETECTION.value: "deepseek/deepseek-v3.2",
    ModelPhase.SYNTHESIS.value: "deepseek/deepseek-v3.2",
    ModelPhase.REVIEW.value: "deepseek/deepseek-v3.2",
    ModelPhase.REVISION.value: "deepseek/deepseek-v3.2",
    ModelPhase.FORMATTING.value: "deepseek/deepseek-v3.2",
}


# PRICING ($/M tokens)


PRICING: Dict[str, Dict[Literal["input", "output"], float]] = {
    # Free models
    "deepseek/deepseek-r1-0528:free": {"input": 0.0, "output": 0.0},
    "qwen/qwen-2.5-7b-instruct:free": {"input": 0.0, "output": 0.0},
    "deepseek/deepseek-r1-distill-qwen-7b:free": {"input": 0.0, "output": 0.0},
    "meta-llama/llama-3.3-70b-instruct:free": {"input": 0.0, "output": 0.0},
    "google/gemma-3-27b:free": {"input": 0.0, "output": 0.0},
    "qwen/qwen-2.5-coder-7b-instruct:free": {"input": 0.0, "output": 0.0},
    
    # Paid models
    "moonshotai/kimi-k2.5": {"input": 0.40, "output": 1.75},
    "deepseek/deepseek-v3.2": {"input": 0.25, "output": 0.38},
}



# MODEL SELECTION FUNCTION


def get_model_for_phase(
    research_mode: ResearchMode | str,
    phase: ModelPhase | str,
    use_deepseek_v3: bool = False,
) -> str:
    """
    Get the appropriate model for a research phase.
    
    Args:
        research_mode: "standard" or "deep"
        phase: Research phase (planning, research, verification, etc.)
        use_deepseek_v3: If True and deep mode, use DeepSeek V3.2 instead of Kimi K2.5
        
    Returns:
        Model ID string for OpenRouter
        
    Example:
        >>> get_model_for_phase("standard", "planning")
        "deepseek/deepseek-r1-0528:free"
        
        >>> get_model_for_phase("deep", "synthesis")
        "moonshotai/kimi-k2.5"
    """
    mode = ResearchMode(research_mode) if isinstance(research_mode, str) else research_mode
    phase_str = phase.value if isinstance(phase, ModelPhase) else phase
    
    if mode == ResearchMode.STANDARD:
        return STANDARD_MODELS[phase_str]
    elif mode == ResearchMode.DEEP:
        if use_deepseek_v3:
            return DEEPSEEK_V3_MODELS[phase_str]
        else:
            return DEEP_MODELS[phase_str]
    else:
        raise ValueError(f"Unknown research mode: {mode}")


def get_model_pricing(model: str) -> Dict[Literal["input", "output"], float]:
    """
    Get pricing for a model.
    
    Args:
        model: Model ID string
        
    Returns:
        Dictionary with "input" and "output" cost per million tokens
        
    Example:
        >>> get_model_pricing("moonshotai/kimi-k2.5")
        {"input": 0.40, "output": 1.75}
    """
    return PRICING.get(model, {"input": 0.0, "output": 0.0})



# OPENROUTER CONFIGURATION


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

OPENROUTER_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": OPENROUTER_API_KEY,
    "default_headers": {
        "HTTP-Referer": "https://consilience.ai",
        "X-Title": "Consilience Research",
    },
}


# MODEL CAPABILITIES


MODEL_CAPABILITIES: Dict[str, Dict[str, bool]] = {
    "deepseek/deepseek-r1-0528:free": {
        "reasoning": True,
        "tool_calling": True,
        "vision": False,
        "long_context": True,  # 164K tokens
    },
    "qwen/qwen-2.5-7b-instruct:free": {
        "reasoning": True,
        "tool_calling": True,
        "vision": False,
        "long_context": True,  # 131K tokens
    },
    "deepseek/deepseek-r1-distill-qwen-7b:free": {
        "reasoning": True,
        "tool_calling": True,
        "vision": False,
        "long_context": False,  # 32K tokens
    },
    "meta-llama/llama-3.3-70b-instruct:free": {
        "reasoning": True,
        "tool_calling": True,
        "vision": False,
        "long_context": True,  # 128K tokens
    },
    "google/gemma-3-27b:free": {
        "reasoning": True,
        "tool_calling": True,  # Structured output support
        "vision": False,
        "long_context": True,  # 128K tokens
    },
    "qwen/qwen-2.5-coder-7b-instruct:free": {
        "reasoning": False,
        "tool_calling": True,
        "vision": False,
        "long_context": True,  # 131K tokens
    },
    "moonshotai/kimi-k2.5": {
        "reasoning": True,
        "tool_calling": True,
        "vision": True,  # Native multimodal
        "long_context": True,  # 256K tokens
        "agent_swarm": True,
        "thinking_mode": True,
    },
    "deepseek/deepseek-v3.2": {
        "reasoning": True,
        "tool_calling": True,
        "vision": False,
        "long_context": True,
    },
}



# MODEL RECOMMENDATIONS BY PHASE

MODEL_DESCRIPTIONS = {
    "deepseek/deepseek-r1-0528:free": {
        "name": "DeepSeek R1-0528",
        "size": "671B (37B active)",
        "context": "164K",
        "use_cases": ["Planning", "Synthesis", "Revision"],
        "why": "Matches OpenAI o1 performance; best reasoning; strong long-form writing",
    },
    "qwen/qwen-2.5-7b-instruct:free": {
        "name": "Qwen 2.5 7B",
        "size": "7B",
        "context": "131K",
        "use_cases": ["Research (parallel)"],
        "why": "Fast parallel execution; multilingual; great for general tasks",
    },
    "deepseek/deepseek-r1-distill-qwen-7b:free": {
        "name": "DeepSeek R1 Distill Qwen 7B",
        "size": "7B",
        "context": "32K",
        "use_cases": ["Verification"],
        "why": "Strong reasoning distilled into small model; fast verification",
    },
    "meta-llama/llama-3.3-70b-instruct:free": {
        "name": "Llama 3.3 70B",
        "size": "70B",
        "context": "128K",
        "use_cases": ["Detection"],
        "why": "Excellent at comparative analysis; large context for many sources",
    },
    "google/gemma-3-27b:free": {
        "name": "Gemma 3 27B",
        "size": "27B",
        "context": "128K",
        "use_cases": ["Review"],
        "why": "Strong instruction following; structured output support",
    },
    "qwen/qwen-2.5-coder-7b-instruct:free": {
        "name": "Qwen 2.5 Coder 7B",
        "size": "7B",
        "context": "131K",
        "use_cases": ["Formatting"],
        "why": "Specialized for structured output; perfect for citations",
    },
    "moonshotai/kimi-k2.5": {
        "name": "Kimi K2.5",
        "size": "Unknown",
        "context": "256K",
        "use_cases": ["Deep Research (all phases)"],
        "why": "Agent swarm + multimodal + 200-300 tool calls + thinking mode",
    },
    "deepseek/deepseek-v3.2": {
        "name": "DeepSeek V3.2",
        "size": "Unknown",
        "context": "Unknown",
        "use_cases": ["Deep Research (budget-constrained)"],
        "why": "40% cheaper than Kimi; GPT-5 class reasoning",
    },
}
