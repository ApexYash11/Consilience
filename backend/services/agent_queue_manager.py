"""
Agent Queue Manager - Simplifies injecting request queue into agents

Provides a clean interface for injecting the OpenRouter request queue
into agents without modifying orchestrator signatures.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global queue reference (set at app startup)
_request_queue: Optional[object] = None


def set_global_request_queue(queue: Optional[object]) -> None:
    """
    Set the global request queue for all agents.
    Called during FastAPI app startup.
    """
    global _request_queue
    _request_queue = queue
    if queue:
        logger.info("Global request queue configured for agents")


def inject_queue_to_agent(agent: object) -> None:
    """
    Inject the global request queue into an agent.
    Safe to call if queue is None (agent will use fallback retry logic).
    
    Args:
        agent: BaseAgent instance to inject queue into
    """
    if _request_queue and hasattr(agent, "set_request_queue"):
        agent.set_request_queue(_request_queue)
        logger.debug(f"Injected queue into agent {getattr(agent, 'agent_name', 'unknown')}")


def get_global_request_queue() -> Optional[object]:
    """Get the current global request queue."""
    return _request_queue
