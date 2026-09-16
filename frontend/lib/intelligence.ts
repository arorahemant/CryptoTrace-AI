import type { TrailTransfer } from './investigation';
import type { DestinationCandidate } from './transfers';

export type RecordReference = { kind: 'wallet' | 'transfer' | 'finding' | 'evidence'; id: string; label: string; source?: string; transaction_hash?: string };
export interface DestinationIntelligence {
  run_id: string | null; network: string; data_origin: string;
  candidate: DestinationCandidate | null;
  attribution: { attribution_status: string; entity_name: string | null; reasoning: string | null; source: string; provenance: string; source_reference: string | null; supporting_evidence_ids: string[]; supporting_transaction_hashes: string[] };
  selection_basis: string; supporting_path: string[]; supporting_transfers: TrailTransfer[];
  evidence: { id: string; title: string; finding_id: string | null; transfer_id: string | null; transaction_hash: string | null; source: string }[];
  findings: { id: string; title: string; transfer_ids: string[]; evidence_ids: string[] }[];
  observation_provider: string | null; external_attribution_provider: string;
  verified_at: string | null; freshness: string; retrieved_at: string | null;
  coverage: { state?: string; partial?: boolean } | null; limitations: string[];
}
export interface CopilotAnswer {
  next_review_step?: string | null;
  answer: string; run_id?: string | null; data_origin: string; attribution_status: string;
  coverage?: { state?: string; partial?: boolean } | null;
  sections: { title: string; items: string[] }[]; supporting_records: RecordReference[];
  sources: string[]; limitations: string[];
}
export const intelligenceLabel = (status?: string) => status === 'known_verified' ? 'VERIFIED' : status === 'likely_inferred' ? 'LIKELY / INFERRED' : 'UNKNOWN';
export const originLabel = (origin?: string) => origin === 'demo' ? 'DEMO DATA' : origin === 'observed' ? 'PROVIDER-OBSERVED DATA' : 'NO OBSERVED DATA';
export const copilotQuestions = ['Explain the observed money trail.', 'Why is this the leading destination?', 'What evidence supports this candidate?', 'What should I review next?', 'Which transfers support this finding?', 'Why was this wallet flagged?', 'What information is still missing?', 'Why is attribution UNKNOWN?'];
