// Presentation only. The server remains authoritative for validation and status.
export const networkOptions = [
  { value: 'demo', label: 'Demo Network', assets: [{ value: 'ETH', label: 'ETH' }], hint: 'Enter a demo wallet address beginning with 0x, followed by at least 8 letters or numbers.' },
  { value: 'ethereum', label: 'Ethereum', assets: [{ value: 'ETH', label: 'ETH' }, { value: 'USDT', label: 'USDT' }, { value: 'USDC', label: 'USDC' }], hint: 'Paste the full 42-character address beginning with 0x.' },
  { value: 'bitcoin', label: 'Bitcoin', assets: [{ value: 'BTC', label: 'BTC' }], hint: 'Paste the full Bitcoin address beginning with bc1, 1, or 3.' },
  { value: 'tron', label: 'Tron', assets: [{ value: 'TRX', label: 'TRX' }, { value: 'USDT', label: 'USDT' }], hint: 'Paste the full 34-character Tron address beginning with T.' },
  { value: 'polygon', label: 'Polygon', assets: [{ value: 'POL', label: 'POL / MATIC' }, { value: 'USDT', label: 'USDT' }, { value: 'USDC', label: 'USDC' }], hint: 'Paste the full 42-character address beginning with 0x.' },
  { value: 'bsc', label: 'BNB Smart Chain', assets: [{ value: 'BNB', label: 'BNB' }, { value: 'USDT', label: 'USDT' }, { value: 'USDC', label: 'USDC' }], hint: 'Paste the full 42-character address beginning with 0x.' },
] as const;

const statuses: Record<string, { label: string; description: string }> = {
  report_received: { label: 'Report received', description: 'Your report is queued for investigator review. Keep your reference ID for future access.' },
  accepted: { label: 'Report accepted', description: 'Your report has been accepted. Wallet activity analysis is currently unavailable for this report.' },
  under_investigation: { label: 'Under investigation', description: 'Your report is assigned for investigation. No action is needed unless more information is requested.' },
  further_review_required: { label: 'Further review required', description: 'The investigation team needs to review this case further.' },
  analysis_completed: { label: 'Analysis completed', description: 'The analysis run has finished. The case remains open and findings still need investigator review.' },
  case_closed: { label: 'Case closed', description: 'The investigator has closed this case. This does not confirm recovery of funds or any external action.' },
};

export function reporterStatus(status: string) {
  return statuses[status] ?? { label: 'Status unavailable', description: 'Your report is saved, but its current status cannot be displayed. Try refreshing later.' };
}

export function walletError(value: string, blockchain: string): string | undefined {
  const address = value.trim();
  if (!address) return 'Paste the wallet address you want to report.';
  const patterns: Record<string, RegExp> = {
    demo: /^0x[A-Za-z0-9]{8,253}$/,
    ethereum: /^0x[0-9a-fA-F]{40}$/,
    polygon: /^0x[0-9a-fA-F]{40}$/,
    bsc: /^0x[0-9a-fA-F]{40}$/,
    bitcoin: /^(?:bc1[a-z0-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$/,
    tron: /^T[1-9A-HJ-NP-Za-km-z]{33}$/,
  };
  const network = networkOptions.find(option => option.value === blockchain);
  if (!patterns[blockchain]?.test(address)) return `This address doesn’t match ${network?.label || 'the selected network'}. ${network?.hint || 'Check the network and address.'}`;
}

export function reporterError(status: number | undefined, action: 'load' | 'submit') {
  if (status === 401 || status === 403) return 'We couldn’t access your reporter account. Please sign out and sign in again.';
  if (action === 'load') return 'We couldn’t load your reports. Check your connection and try again.';
  if (status === 400 || status === 422) return 'We couldn’t accept these details. Check the wallet address, network, and report title, then try again.';
  if (status === 429) return 'Too many attempts. Please wait a moment before trying again.';
  return 'We couldn’t confirm your submission. Check your reports before submitting again to avoid sending the same report twice.';
}

export function formatReportDate(value?: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
