export interface CapabilityState {
  run_id?: string | null;
  model_version?: number | null;
  data_origin: 'none' | 'demo' | 'observed';
  provider_state: 'available' | 'not_connected';
  processing_state: 'not_started' | 'running' | 'completed' | 'failed';
  result_state: 'not_available' | 'available' | 'empty' | 'partial' | 'stale';
  provider: string | null;
  processed_at: string | null;
  data_as_of: string | null;
  limitations: string[];
  can_investigate?: boolean;
  observation_state?: string | null;
  coverage?: {
    state?: string; partial?: boolean; exhausted?: boolean; run_id?: string;
    observation_boundaries?: { from_block?: number; to_block?: number; max_hops?: number };
    requested_block_range?: { from_block?: number; to_block?: number | null };
    provider_requests?: number; retrieved_at?: string;
    provider_errors?: { code: string }[];
  } | null;
  destination?: { address: string; kind: string } | null;
}

export interface NetworkCapability {
  blockchain: string;
  assets: string[];
  capability: CapabilityState;
}

export function capabilityLabel(state?: CapabilityState): string {
  if (!state) return 'NOT AVAILABLE — capability could not be loaded';
  const origin = state.data_origin === 'demo' ? 'DEMO DATA' : state.data_origin === 'observed' ? 'OBSERVED DATA' : 'NO OBSERVED DATA';
  if (state.provider === 'alchemy_ethereum') return `${origin} ? ${(state.observation_state || 'not_verified').replaceAll('_', ' ').toUpperCase()} ? ${state.processing_state.toUpperCase()}`;
  if (state.provider_state === 'not_connected') return `${origin} · PROVIDER NOT CONNECTED`;
  if (state.processing_state === 'failed') return `${origin} · FAILED`;
  if (state.processing_state === 'running') return `${origin} · PROCESSING`;
  if (state.result_state === 'not_available') return `${origin} · PROVIDER AVAILABLE · NO RESULT YET`;
  return `${origin} · ${state.result_state.toUpperCase()}${state.processing_state === 'completed' ? ' · PROCESSING COMPLETED' : ''}`;
}

export function hasAnalysis(state?: CapabilityState): boolean {
  return !!state && state.data_origin !== 'none' && ['available', 'partial', 'stale'].includes(state.result_state);
}
