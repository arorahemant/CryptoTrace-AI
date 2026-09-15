export interface ExactTransfer {
  block_number?: number | null;
  block_hash?: string | null;
  log_index?: number | null;
  transaction_status?: string | null;
  token_contract?: string | null;
  provenance?: Record<string, unknown> | null;
  transfer_id?: string;
  run_id?: string;
  chain_id?: string;
  event_index?: string;
  asset_id?: string;
  amount_base_units?: string | null;
  token_decimals?: number | null;
  amount_exact?: string | null;
  amount_precision?: 'exact' | 'legacy_approximate';
}

export interface AssetTotal {
  asset_id: string;
  asset: string;
  amount_base_units: string;
  token_decimals: number;
  amount_exact: string;
}

export interface DestinationCandidate {
  address: string;
  kind: 'identified_service_address' | 'candidate_vasp' | 'last_observed_wallet' | 'not_expanded';
  expansion_state: string;
  hop_distance: number;
  attribution_status: string;
}

export function displayAmount(value: ExactTransfer & { amount?: number | null }): string {
  return value.amount_precision === 'exact' && value.amount_exact != null
    ? value.amount_exact : value.amount != null ? `≈${value.amount}` : 'Unavailable';
}

export function displayTotals(totals?: AssetTotal[]): string {
  return totals?.length ? totals.map(t => `${t.amount_exact} ${t.asset} [${t.asset_id}]`).join('; ') : 'Unavailable';
}
