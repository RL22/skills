/**
 * Production-Grade Graph Execution Engine Template
 * SkillVault Version: 2.0.0
 */

export interface GraphState {
  taskId: string;
  userGoal: string;
  category?: string;
  contextData?: Record<string, any>;
  draftOutput?: string;
  verificationLogs: string[];
  skepticFlaws: string[];
  isVerified: boolean;
  isApproved: boolean;
  retryCount: number;

  // Loop & Termination Guardrails
  maxIterations: number; // Recommended default: 3
  iterationCount: number;
  failureReason?: string;

  // Branching & Diamond Pattern State
  parallelBranchResults?: Record<string, any>;
  branchSelected?: string;
}

export type ModelTier = 'tier0' | 'tier1' | 'tier2' | 'tier3';

export interface NodeConfig {
  id: string;
  name: string;
  tier: ModelTier;
  effort: 'N/A' | 'Light' | 'Medium' | 'High';
  modelTarget: string;
}

export interface BranchTask<T = any> {
  branchId: string;
  nodeConfig?: NodeConfig;
  execute: (currentState: GraphState) => Promise<T>;
}

/**
 * Factory helper to initialize a clean GraphState with safe guardrail defaults
 */
export function createInitialGraphState(
  taskId: string,
  userGoal: string,
  overrides?: Partial<GraphState>
): GraphState {
  return {
    taskId,
    userGoal,
    verificationLogs: [],
    skepticFlaws: [],
    isVerified: false,
    isApproved: false,
    retryCount: 0,
    maxIterations: 3,
    iterationCount: 0,
    ...overrides,
  };
}

export function routeNodeModel(tier: ModelTier, retryCount = 0): NodeConfig['modelTarget'] {
  // Escalation rule: Escalate to Tier 3 reasoning on repeated failures
  if (retryCount >= 2) {
    return 'openai/5.6-sol-high';
  }

  switch (tier) {
    case 'tier1':
      return 'anthropic/claude-haiku-4.5';
    case 'tier2':
      return 'anthropic/claude-sonnet-5';
    case 'tier3':
      return 'openai/5.6-sol-high';
    default:
      return 'deterministic-script';
  }
}

/**
 * Standard Node Execution Function Wrapper
 */
export async function executeGraphNode(
  nodeConfig: NodeConfig,
  state: GraphState,
  nodeLogic: (currentState: GraphState) => Promise<Partial<GraphState>>
): Promise<GraphState> {
  console.log(`[Graph Node Executing] ${nodeConfig.name} (${nodeConfig.tier} - Effort: ${nodeConfig.effort})`);
  
  const stateUpdate = await nodeLogic(state);
  
  return {
    ...state,
    ...stateUpdate
  };
}

/**
 * Guardrail: Rule of Five
 * Throws an error or warns if branch count exceeds 5, preventing overengineered router nodes.
 *
 * @param branches - Array of branch names or branch identifiers
 * @param warnOnly - If true, emits a console warning instead of throwing an error (default: false)
 */
export function assertRuleOfFive(branches: string[], warnOnly = false): void {
  const MAX_BRANCHES = 5;
  if (branches.length > MAX_BRANCHES) {
    const message = `[Rule of Five Guardrail] Branch count (${branches.length}) exceeds maximum limit of ${MAX_BRANCHES}: [${branches.join(', ')}]. Avoid overengineered router nodes; decompose into hierarchical sub-routers.`;
    if (warnOnly) {
      console.warn(message);
    } else {
      console.error(message);
      throw new Error(message);
    }
  }
}

/**
 * Wrapper for loop evaluation that checks iteration bounds against maxIterations.
 * If exceeded, trips the circuit breaker, sets failureReason = 'MAX_ITERATIONS_EXCEEDED',
 * and escalates rather than looping infinitely.
 *
 * @param nodeConfig - Configuration metadata for the loop node
 * @param state - Current GraphState
 * @param nodeLogic - Execution/evaluation logic for this iteration
 * @param onEscalate - Optional custom escalation handler invoked when circuit breaker trips
 */
export async function executeLoopNode(
  nodeConfig: NodeConfig,
  state: GraphState,
  nodeLogic: (currentState: GraphState) => Promise<Partial<GraphState>>,
  onEscalate?: (currentState: GraphState) => Promise<Partial<GraphState>>
): Promise<GraphState> {
  const maxIterations = state.maxIterations ?? 3;
  const currentIterations = state.iterationCount ?? 0;

  if (currentIterations >= maxIterations) {
    console.warn(
      `[Circuit Breaker] Max iterations (${maxIterations}) exceeded at node '${nodeConfig.name}'. Escalating rather than looping infinitely.`
    );

    const escalatedState: GraphState = {
      ...state,
      failureReason: 'MAX_ITERATIONS_EXCEEDED',
      retryCount: (state.retryCount ?? 0) + 1,
    };

    if (onEscalate) {
      const escalationUpdates = await onEscalate(escalatedState);
      return {
        ...escalatedState,
        ...escalationUpdates,
      };
    }

    return escalatedState;
  }

  console.log(
    `[Loop Node Evaluating] ${nodeConfig.name} (${nodeConfig.tier} - Effort: ${nodeConfig.effort}) [Iteration ${currentIterations + 1}/${maxIterations}]`
  );

  const nextState: GraphState = {
    ...state,
    iterationCount: currentIterations + 1,
  };

  const stateUpdate = await nodeLogic(nextState);

  return {
    ...nextState,
    ...stateUpdate,
  };
}

/**
 * Helper that runs an array of independent branch tasks in parallel (using Promise.allSettled),
 * verifies no silent failures occurred, and produces a merged payload.
 *
 * @param state - Current GraphState
 * @param branchTasks - Array of independent branch tasks to execute concurrently
 * @param mergePayload - Optional custom reducer to merge branch results into state
 */
export async function executeDiamondFanout(
  state: GraphState,
  branchTasks: BranchTask[],
  mergePayload?: (results: Record<string, any>, currentState: GraphState) => Partial<GraphState>
): Promise<GraphState> {
  // Guardrail: Assert maximum of 5 branches before parallel execution
  assertRuleOfFive(branchTasks.map((b) => b.branchId));

  console.log(
    `[Diamond Fanout Executing] Running ${branchTasks.length} parallel branches: ${branchTasks.map((b) => b.branchId).join(', ')}`
  );

  const taskPromises = branchTasks.map(async (branch) => {
    const result = await branch.execute(state);
    return { branchId: branch.branchId, result };
  });

  const settledResults = await Promise.allSettled(taskPromises);

  const errors: Array<{ branchId: string; reason: any }> = [];
  const mergedPayload: Record<string, any> = {};

  settledResults.forEach((outcome, index) => {
    const branch = branchTasks[index];
    if (outcome.status === 'fulfilled') {
      mergedPayload[outcome.value.branchId] = outcome.value.result;
    } else {
      errors.push({
        branchId: branch.branchId,
        reason: outcome.reason,
      });
    }
  });

  // Verify no silent failures occurred
  if (errors.length > 0) {
    const errorDetails = errors
      .map(
        (err) =>
          `[Branch '${err.branchId}']: ${err.reason instanceof Error ? err.reason.message : String(err.reason)}`
      )
      .join('; ');
    const errorMessage = `[Diamond Fanout Failure] ${errors.length} parallel branch(es) failed: ${errorDetails}`;
    console.error(errorMessage);
    throw new Error(errorMessage);
  }

  const updatedParallelResults = {
    ...(state.parallelBranchResults || {}),
    ...mergedPayload,
  };

  const baseNextState: GraphState = {
    ...state,
    parallelBranchResults: updatedParallelResults,
  };

  if (mergePayload) {
    const customMergedState = mergePayload(mergedPayload, baseNextState);
    return {
      ...baseNextState,
      ...customMergedState,
    };
  }

  return baseNextState;
}

/**
 * Helper to execute a dynamic branch selection router node.
 * Enforces the Rule of Five guardrail and updates branchSelected on GraphState.
 */
export async function executeRouterNode(
  nodeConfig: NodeConfig,
  state: GraphState,
  routerLogic: (currentState: GraphState) => Promise<string> | string,
  validBranches: string[]
): Promise<GraphState> {
  assertRuleOfFive(validBranches);
  console.log(`[Router Node Executing] ${nodeConfig.name} (${nodeConfig.tier})`);

  const selected = await routerLogic(state);
  if (!validBranches.includes(selected)) {
    throw new Error(
      `[Router Node Error] Selected branch '${selected}' is not in valid branch list: [${validBranches.join(', ')}]`
    );
  }

  return {
    ...state,
    branchSelected: selected,
  };
}
