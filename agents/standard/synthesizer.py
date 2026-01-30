"""Synthesizer agent that builds a draft paper from verified sources."""

from langchain_openai import ChatOpenAI
from typing import List, Tuple, Dict, Any
from models.research import Contradiction, ResearchState, Source, TaskStatus
from config.models import (
    get_model_for_phase,
    ModelPhase,
    ResearchMode,
    OPENROUTER_CONFIG,
)
from utils.cost_estimator import estimate_cost_from_response
import logging

logger = logging.getLogger(__name__)


def synthesizer_node(state: ResearchState) -> ResearchState:
    """Generate a draft paper combining verified sources into coherent sections."""
    try:
        sources = state.verified_sources or []
        if not sources:
            logger.warning("Synthesizer received no verified sources")
            state.draft_paper = f"# {state.topic}\n\nNo verified sources available for synthesis."
            return state

        model = get_model_for_phase(
            research_mode=ResearchMode.STANDARD,
            phase=ModelPhase.SYNTHESIS,
        )

        llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            max_completion_tokens=8000,
            **OPENROUTER_CONFIG,
        )

        outline, outline_cost = _create_outline(state.topic, sources, llm, model)
        state.draft_outline = outline

        paper = f"# {state.topic}\n\n"
        for idx, section_title in enumerate(outline, start=1):
            content, section_cost = _write_section(
                topic=state.topic,
                section_title=section_title,
                section_num=idx,
                sources=sources,
                contradictions=state.contradictions or [],
                llm=llm,
                model=model,
            )
            paper += f"## {idx}. {section_title}\n\n{content}\n\n"
            # Accumulate tokens and cost for this section
            try:
                state.tokens_used = (state.tokens_used or 0) + int(section_cost.get("total_tokens", 0))
                state.cost = (state.cost or 0.0) + float(section_cost.get("cost", 0.0))
            except Exception:
                # TODO: Improve fallback estimation for synthesizer section cost
                state.tokens_used = (state.tokens_used or 0) + 0
                state.cost = (state.cost or 0.0)

        bibliography = _generate_bibliography(sources)
        paper += f"## References\n\n{bibliography}\n"

        state.draft_paper = paper
        # Accumulate tokens/cost from outline phase
        try:
            state.tokens_used = (state.tokens_used or 0) + int(outline_cost.get("total_tokens", 0))
            state.cost = (state.cost or 0.0) + float(outline_cost.get("cost", 0.0))
        except Exception:
            # TODO: If cost estimation is deferred, consider a conservative token estimate here
            state.tokens_used = (state.tokens_used or 0) + 0
            state.cost = (state.cost or 0.0)

        logger.info("Draft paper synthesized from verified sources")
        return state

    except Exception as exc:
        logger.error("Synthesizer node failed", exc_info=True)
        state.status = TaskStatus.FAILED
        raise ValueError(f"Synthesis failed: {str(exc)}") from exc


def _create_outline(topic: str, sources: List[Source], llm: ChatOpenAI, model: str) -> Tuple[List[str], Dict[str, Any]]:
    """Generate a paper outline structure."""
    prompt = f"""Create a 7-section research paper outline for: {topic}

Based on {len(sources)} academic sources.

Return only the section titles, one per line:"""
    
    response = llm.invoke(prompt)
    text = response.content if isinstance(response.content, str) else str(response.content)
    sections = [stripped for line in text.split('\n') if (stripped := line.strip()) and not stripped[0].isdigit()]
    
    # Estimate cost for outline generation
    try:
        cost_info = estimate_cost_from_response(response, model)
    except Exception:
        cost_info = {"total_tokens": 0, "cost": 0.0}

    if len(sections) >= 7:
        return sections[:7], cost_info
    return [
        "Introduction",
        "Background & Context",
        "Key Findings",
        "Areas of Debate",
        "Current Research Gaps",
        "Future Directions",
        "Conclusion",
    ], cost_info


def _write_section(
    topic: str,
    section_title: str,
    section_num: int,
    sources: List[Source],
    contradictions: List[Contradiction],
    llm: ChatOpenAI,
    model: str,
) -> Tuple[str, Dict[str, Any]]:
    """Generate content for a single section."""
    is_debate_section = "debate" in section_title.lower() or "conflict" in section_title.lower()
    
    if is_debate_section and contradictions:
        contradiction_summary = "\n".join(
            [f"- {c.severity.upper()}: {c.description}" for c in contradictions[:5]]
        )
        prompt = f"""Write a scholarly section on areas of debate for: {topic}

Include these contradictions:
{contradiction_summary}

Make it 300-500 words, academic tone."""
    else:
        source_refs = "\n".join([f"- {s.title} ({s.year})" for s in sources[:5]])
        prompt = f"""Write section {section_num}: "{section_title}" for a research paper on: {topic}

Use these sources:
{source_refs}

Make it 300-500 words, academic tone."""
    
    response = llm.invoke(prompt)
    content = response.content if isinstance(response.content, str) else str(response.content)
    try:
        cost_info = estimate_cost_from_response(response, model)
    except Exception:
        cost_info = {"total_tokens": 0, "cost": 0.0}
    return content, cost_info


def _generate_bibliography(sources: List[Source]) -> str:
    """Create a bibliography from sources."""
    entries = []
    for idx, source in enumerate(sources, start=1):
        citation = f"{idx}. {source.authors} ({source.year}). {source.title}. {source.publication}."
        if source.doi:
            citation += f" https://doi.org/{source.doi}"
        elif source.url:
            citation += f" Retrieved from {source.url}"
        entries.append(citation)
    return "\n".join(entries) if entries else "No sources cited."