"""
State serialization utilities for observability.

Provides compact serialization of ResearchState for tracing without
creating excessive data in LangSmith.
"""

import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class StateSnapshotEncoder(json.JSONEncoder):
    """Custom JSON encoder for ResearchState snapshots."""
    
    def default(self, o: Any) -> Any:
        """Handle non-standard types."""
        if isinstance(o, (datetime, UUID)):
            return str(o)
        if hasattr(o, "model_dump"):  # Pydantic v2
            return o.model_dump()
        if hasattr(o, "dict"):  # Pydantic v1
            return o.dict()
        return super().default(o)


def serialize_state_compact(state: Any) -> Dict[str, Any]:
    """Serialize ResearchState into a compact representation for tracing.
    
    Captures essential information without full object serialization:
    - Counts (sources, contradictions, etc.)
    - Scores and metrics
    - Key strings (topic, status)
    - Flags (revision_needed, fallback_triggered)
    
    Args:
        state: ResearchState object
        
    Returns:
        Compact dict suitable for LangSmith metadata/feedback.
    """
    try:
        snapshot = {
            "task_id": str(getattr(state, "task_id", "") or ""),
            "topic": (getattr(state, "topic", "") or "")[:100],  # Limit to 100 chars, handle None
            "status": str(getattr(state, "status", "pending") or "pending"),
            "revision_needed": bool(getattr(state, "revision_needed", False) or False),
            "fallback_triggered": bool(getattr(state, "fallback_triggered", False) or False),
            
            # Counts - default to 0-length list if None
            "num_sources": len(getattr(state, "sources", None) or []),
            "num_verified_sources": len(getattr(state, "verified_sources", None) or []),
            "num_contradictions": len(getattr(state, "contradictions", None) or []),
            "num_issues_found": len(getattr(state, "issues_found", None) or []),
            "num_errors": len(getattr(state, "errors", None) or []),
            
            # Scores and metrics - default to 0 if None
            "synthesis_confidence": float(getattr(state, "synthesis_confidence", None) or 0.0),
            "source_quality_score": float(getattr(state, "source_quality_score", None) or 0.0),
            "cost": float(getattr(state, "cost", None) or 0.0),
            "tokens_used": int(getattr(state, "tokens_used", None) or 0),
            
            # Revision tracking - default to 0 if None
            "current_revision_attempt": int(getattr(state, "current_revision_attempt", None) or 0),
            "verifier_rejection_count": int(getattr(state, "verifier_rejection_count", None) or 0),
        }
        
        # Add output lengths if available
        draft_paper = getattr(state, "draft_paper", "")
        if draft_paper:
            snapshot["draft_paper_length"] = len(draft_paper)
        
        final_paper = getattr(state, "final_paper", "")
        if final_paper:
            snapshot["final_paper_length"] = len(final_paper)
        
        return snapshot
    except Exception as e:
        logger.warning(f"Failed to serialize state: {str(e)}")
        return {"error": "serialization_failed"}


def serialize_state_with_inputs(state: Any) -> Dict[str, Any]:
    """Serialize ResearchState including input/plan information.
    
    This is more detailed than compact serialization, including:
    - Research queries
    - Main outline points
    - Verification notes summary
    
    Args:
        state: ResearchState object
        
    Returns:
        Medium-detail dict for debugging/replay.
    """
    compact = serialize_state_compact(state)
    
    try:
        # Add query information
        queries = getattr(state, "research_queries", [])
        if queries:
            compact["research_queries"] = [q[:80] for q in queries[:5]]  # First 5, 80 chars each
        
        # Add outline points
        outline = getattr(state, "draft_outline", [])
        if outline:
            compact["draft_outline_points"] = len(outline)
            compact["outline_sample"] = [p[:60] for p in outline[:3]]  # First 3 points
        
        # Add plan summary
        plan = getattr(state, "research_plan", "")
        if plan:
            compact["research_plan_length"] = len(plan)
        
        # Add first error if any
        errors = getattr(state, "errors", [])
        if errors:
            compact["first_error"] = str(errors[0])[:100]
        
        return compact
    except Exception as e:
        logger.warning(f"Failed to add inputs to state serialization: {str(e)}")
        return compact


def serialize_state_full_json(state: Any) -> str:
    """Fully serialize ResearchState to JSON string.
    
    Used for export/replay: captures all information for reproduction.
    
    Args:
        state: ResearchState object
        
    Returns:
        JSON string representation (lossy for complex objects).
    """
    try:
        if hasattr(state, "model_dump"):  # Pydantic v2
            state_dict = state.model_dump(mode="json")
        elif hasattr(state, "dict"):  # Pydantic v1
            state_dict = state.dict()
        else:
            state_dict = vars(state)
        
        return json.dumps(state_dict, cls=StateSnapshotEncoder, indent=2)
    except Exception as e:
        logger.warning(f"Failed to create full state JSON: {str(e)}")
        return "{}"


def extract_state_delta(state_before: Any, state_after: Any) -> Dict[str, Any]:
    """Extract the changes between two state snapshots.
    
    Useful for understanding what an agent changed.
    
    Args:
        state_before: Previous ResearchState
        state_after: Updated ResearchState
        
    Returns:
        Dict of changed fields with before/after values.
    """
    delta = {}
    
    try:
        # Compare counts
        before_compact = serialize_state_compact(state_before)
        after_compact = serialize_state_compact(state_after)
        
        # Iterate over union of keys to catch additions and removals
        all_keys = set(before_compact.keys()) | set(after_compact.keys())
        
        for key in all_keys:
            before_val = before_compact.get(key)
            after_val = after_compact.get(key)
            
            if before_val != after_val:
                delta[key] = {
                    "before": before_val,
                    "after": after_val,
                }
        
        return delta
    except Exception as e:
        logger.warning(f"Failed to extract state delta: {str(e)}")
        return {}


def get_state_summary(state: Any) -> str:
    """Get a human-readable summary of research state.
    
    Args:
        state: ResearchState object
        
    Returns:
        Single-line summary like: "3 sources (2 verified), confidence 0.82, cost $0.12"
    """
    try:
        num_sources = len(getattr(state, "sources", []))
        num_verified = len(getattr(state, "verified_sources", []))
        confidence = float(getattr(state, "synthesis_confidence", 0.0))
        cost = float(getattr(state, "cost", 0.0))
        
        return (
            f"{num_sources} sources ({num_verified} verified), "
            f"confidence {confidence:.2f}, "
            f"cost ${cost:.2f}"
        )
    except Exception as e:
        logger.debug(f"Failed to create state summary: {str(e)}")
        return "state summary unavailable"
