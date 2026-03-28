export type ResearchStep =
  | "queued"
  | "planning"
  | "researching"
  | "verifying"
  | "detecting"
  | "synthesizing"
  | "reviewing"
  | "formatting"
  | "completed"
  | "failed";

export type AgentState = "waiting" | "running" | "done";

export interface Source {
  id?: string;
  url: string;
  title: string;
  qualityScore?: number;
}

export interface ResearchStatus {
  id: string;
  progress: number;
  currentStep: ResearchStep;
  sources?: Source[];
  tokens?: number;
  costPerToken?: number;
  estimatedRemaining?: string;
  model?: string;
  error?: string;
  status?: "queued" | "processing" | "completed" | "failed";
}

export interface Agent {
  id: string;
  name: string;
  description?: string;
  isGroup?: boolean;
  groupSize?: number;
}

export const AGENTS_LIST: Agent[] = [
  { id: "planner", name: "Planner", description: "Breaks down research into verifiable claims" },
  {
    id: "researcher",
    name: "Researcher",
    description: "Executes parallel searches",
    isGroup: true,
    groupSize: 5,
  },
  { id: "verifier", name: "Verifier", description: "Validates sources and citations" },
  { id: "detector", name: "Detector", description: "Identifies hallucinations" },
  { id: "synthesizer", name: "Synthesizer", description: "Synthesizes research into paper" },
  { id: "reviewer", name: "Reviewer", description: "Critiques methodology" },
  { id: "formatter", name: "Formatter", description: "Produces publication-ready output" },
];
