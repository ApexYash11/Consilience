import type { ResearchStep, AgentState } from "@/types/research";

/**
 * Maps a research step to agent states deterministically.
 * Each step has a specific sequence of agents running.
 */
export function mapStepToAgents(step: ResearchStep): Record<string, AgentState> {
  const agentIds = ["planner", "researcher", "verifier", "detector", "synthesizer", "reviewer", "formatter"];

  // Initialize all agents as waiting
  const states: Record<string, AgentState> = Object.fromEntries(
    agentIds.map((id) => [id, "waiting" as AgentState])
  );

  // Map each step to its active agents
  switch (step) {
    case "queued":
    case "planning":
      states.planner = "running";
      break;

    case "researching":
      states.planner = "done";
      states.researcher = "running";
      break;

    case "verifying":
      states.planner = "done";
      states.researcher = "done";
      states.verifier = "running";
      break;

    case "detecting":
      states.planner = "done";
      states.researcher = "done";
      states.verifier = "done";
      states.detector = "running";
      break;

    case "synthesizing":
      states.planner = "done";
      states.researcher = "done";
      states.verifier = "done";
      states.detector = "done";
      states.synthesizer = "running";
      break;

    case "reviewing":
      states.planner = "done";
      states.researcher = "done";
      states.verifier = "done";
      states.detector = "done";
      states.synthesizer = "done";
      states.reviewer = "running";
      break;

    case "formatting":
      states.planner = "done";
      states.researcher = "done";
      states.verifier = "done";
      states.detector = "done";
      states.synthesizer = "done";
      states.reviewer = "done";
      states.formatter = "running";
      break;

    case "completed":
      agentIds.forEach((id) => {
        states[id] = "done";
      });
      break;

    case "failed":
      // Freeze state when failed - don't mark everything as done
      break;

    default:
      // Runtime error for unknown steps - fail fast
      throw new Error(`Unknown research step: "${step}". Expected one of: queued, planning, researching, verifying, detecting, synthesizing, reviewing, formatting, completed, failed`);
  }

  return states;
}
