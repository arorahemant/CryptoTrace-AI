import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { selectedPath, layoutGraph, projectPoint, boundaryLabel, walletRole } from './investigation.ts';
import { displayAmount } from './transfers.ts';

// Public receipt already captured and approved in Phase 2B; never fetched live.
const capture = JSON.parse(readFileSync(new URL('../../backend/tests/fixtures/phase2b_alchemy.json', import.meta.url)));
const receipt = capture.responses.find(r => r.method === 'eth_getTransactionReceipt').result;
const transferLogs = receipt.logs.filter(log => log.topics[0] === '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef');
const edges = transferLogs.map(log => ({
  id: JSON.stringify(['1', log.transactionHash, String(parseInt(log.logIndex, 16))]),
  source: '0x' + log.topics[1].slice(-40), target: '0x' + log.topics[2].slice(-40),
  hash: log.transactionHash, amount_base_units: BigInt(log.data).toString(), block_hash: log.blockHash,
  event_index: String(parseInt(log.logIndex, 16)),
}));
const addresses = [...new Set(edges.flatMap(edge => [edge.source, edge.target]))];
const graph = { run_id: 'captured-response-validation', nodes: addresses.map((address, index) => ({ address, is_reported: index === 0, hop_distance: index === 0 ? 0 : 1, expansion_state: 'expanded' })), edges, primary_path: [] };

test('2D and 3D layout keeps every captured wallet and event, without mutating data', () => {
  const before = JSON.stringify(graph);
  const layout = layoutGraph(graph);
  assert.equal(layout.length, graph.nodes.length);
  assert.equal(new Set(graph.edges.map(e => e.id)).size, transferLogs.length);
  layout.forEach((point, i) => { assert.equal(point.node, graph.nodes[i]); assert.ok(Number.isFinite(projectPoint(point, .5, .4, .7).x)); });
  assert.equal(JSON.stringify(graph), before);
});
test('multiple receipt events remain independently selectable by identity', () => {
  assert.ok(edges.length > 1);
  for (const edge of edges) {
    const selected = selectedPath(graph, { wallets: [edge.source, edge.target], transfers: [edge.id], label: 'Event' });
    assert.ok(selected.transfers.has(edge.id));
    assert.ok(selected.wallets.has(edge.source));
    assert.ok(selected.wallets.has(edge.target));
  }
});
test('parallel events do not select the first sibling when the second is requested', () => {
  const first = edges[0];
  // UI topology regression only, not a blockchain observation or runtime data.
  const fixture = { ...graph, nodes: [{ address: first.source, is_reported: true }, { address: first.target }], edges: [{ ...first, id: 'event-a' }, { ...first, id: 'event-b' }] };
  assert.deepEqual([...selectedPath(fixture, { wallets: [first.source, first.target], transfers: ['event-b'] }).transfers], ['event-b']);
});
test('directed cyclic topology terminates and never invents connections', () => {
  const edge = edges[0];
  const cyclic = { ...graph, edges: [edge, { ...edge, id: 'return-edge', source: edge.target, target: edge.source }] };
  const result = selectedPath(cyclic, { wallets: [edge.target], transfers: [], label: 'Wallet' });
  assert.ok([...result.transfers].every(id => cyclic.edges.some(e => e.id === id)));
});
test('empty graph and missing expansion metadata are truthful', () => {
  assert.equal(selectedPath({ nodes: [], edges: [], primary_path: [] }, null).wallets.size, 0);
  assert.equal(boundaryLabel({ address: addresses[0] }), 'Expansion unknown');
  assert.match(boundaryLabel({ address: addresses[0], expansion_state: 'hop_limit' }), /Not expanded/);
  assert.equal(walletRole({ address: addresses[0] }, addresses[0]), 'Destination candidate');
});
test('display uses exact decimal strings even when legacy float disagrees', () => {
  assert.equal(displayAmount({ amount_precision: 'exact', amount_exact: '1.000000000000000001', amount: 2 }), '1.000000000000000001');
  assert.equal(displayAmount({ amount_precision: 'exact', amount_base_units: edges[0].amount_base_units }), 'Unavailable');
});
test('projection rotates depth without altering authoritative values', () => {
  const point = { x: 300, y: 40, z: 100 };
  assert.notDeepEqual(projectPoint(point, 0, 0, 1), projectPoint(point, Math.PI / 2, .5, 1));
  assert.deepEqual(point, { x: 300, y: 40, z: 100 });
});

// Exercise actual inspector markup without adding a browser or test framework.
const require = createRequire(import.meta.url);
function component(name) {
  const source = readFileSync(new URL(`../components/investigation/${name}.tsx`, import.meta.url), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const compiled = { exports: {} };
  const load = path => path.startsWith('@/lib/') ? require(`./${path.slice(6)}.ts`) : require(path);
  new Function('require', 'module', 'exports', output)(load, compiled, compiled.exports);
  return compiled.exports;
}
const { TransferInspector, WalletInspector } = component('RecordInspector');
const { CoverageStrip } = component('CoverageStrip');
const noop = () => {};
const capability = { data_origin: 'observed', provider_state: 'available', processing_state: 'completed', result_state: 'partial', observation_state: 'partial', provider: 'Alchemy', run_id: graph.run_id, limitations: ['Historical interval only'], coverage: { partial: true, exhausted: false, observation_boundaries: { from_block: parseInt(receipt.blockNumber, 16), to_block: parseInt(receipt.blockNumber, 16) } } };
test('transfer inspector renders captured event identity, raw units and missing metadata', () => {
  const edge = edges[0];
  const html = renderToStaticMarkup(React.createElement(TransferInspector, { transfer: { ...edge, transfer_id: edge.id, from_address: edge.source, to_address: edge.target, asset: 'ERC-20', amount_precision: 'exact' }, network: 'ethereum', capability, canSave: false, saving: false, message: '', onSave: noop, onClose: noop, onWallet: noop, onFocus: noop }));
  assert.ok(html.includes(edge.amount_base_units));
  assert.ok(html.includes('METADATA UNAVAILABLE'));
  assert.ok(html.includes('PARTIAL'));
  assert.ok(html.includes(`https://etherscan.io/tx/${edge.hash}`));
  assert.ok(!html.includes('Add evidence'));
  assert.ok(!html.includes('VERIFIED'));
});
test('demo inspector never links a synthetic transaction to Mainnet explorer', () => {
  const html = renderToStaticMarkup(React.createElement(TransferInspector, { transfer: { hash: edges[0].hash, from_address: addresses[0], to_address: addresses[1], asset: 'ETH', amount_exact: '1.000000000000000001', amount_precision: 'exact' }, network: 'demo', capability: { ...capability, data_origin: 'demo' }, canSave: true, saving: false, message: '', onSave: noop, onClose: noop, onWallet: noop, onFocus: noop }));
  assert.ok(html.includes('1.000000000000000001'));
  assert.ok(html.includes('DEMO DATA'));
  assert.ok(html.includes('Add evidence'));
  assert.ok(!html.includes('etherscan.io'));
});
test('wallet inspector exposes expansion and unknown attribution without inventing an entity', () => {
  const html = renderToStaticMarkup(React.createElement(WalletInspector, { wallet: { address: addresses[0], expansion_state: 'hop_limit', hop_distance: 2 }, network: 'Ethereum Mainnet', onClose: noop, onTransfers: noop, onEvidence: noop, onWhy: noop, onFocus: noop }));
  assert.ok(html.includes('UNKNOWN'));
  assert.ok(html.includes('Not expanded'));
  assert.ok(html.includes('Why this wallet?'));
  assert.ok(!html.includes('VERIFIED'));
});
test('coverage keeps failed attempts and non-exhausted historical bounds explicit', () => {
  const html = renderToStaticMarkup(React.createElement(CoverageStrip, { capability: { ...capability, data_origin: 'none', processing_state: 'failed' } }));
  assert.ok(html.includes('ATTEMPT FAILED'));
  assert.ok(html.includes('NO OBSERVED DATA'));
  assert.ok(html.includes(graph.run_id));
  assert.ok(html.includes('Historical interval only'));
});

const highActivity = JSON.parse(readFileSync(new URL('../../backend/tests/fixtures/high_activity_alchemy.json', import.meta.url)));
const observedGraph = highActivity.graph;
const { default: Network3D } = component('Network3D');
const { DestinationIntelligencePanel, CopilotPanel, ActionReadinessSummary } = component('IntelligencePanels');
const highIntelligence = {
  run_id: observedGraph.run_id, network: 'ethereum', data_origin: 'observed', candidate: observedGraph.destination,
  attribution: { attribution_status: 'unknown', entity_name: null, reasoning: 'Attribution is unavailable or insufficiently supported.', source: 'unknown', provenance: 'unknown', source_reference: null, supporting_evidence_ids: [], supporting_transaction_hashes: [] },
  selection_basis: 'Current bounded observation', supporting_path: observedGraph.primary_path,
  supporting_transfers: observedGraph.edges.filter(e => e.target === observedGraph.destination.address), evidence: [], findings: [],
  observation_provider: 'alchemy_ethereum', external_attribution_provider: 'not_connected', verified_at: null, freshness: 'unknown',
  retrieved_at: highActivity.capability.coverage.retrieved_at, coverage: highActivity.capability.coverage, limitations: ['Observed connections do not establish ownership.'],
};

test('destination intelligence presents real partial observations with unknown attribution', () => {
  const html = renderToStaticMarkup(React.createElement(DestinationIntelligencePanel, { data: highIntelligence, onSelect: noop }));
  for (const label of ['PROVIDER-OBSERVED DATA', 'PARTIAL', 'UNKNOWN', 'NOT CONNECTED', 'NOT AVAILABLE', observedGraph.destination.address]) assert.ok(html.includes(label));
  assert.ok(!html.includes('VERIFIED'));
  assert.ok(!html.includes('Freeze Wallet'));
});

test('attribution labels remain distinct and untrusted source text is escaped', () => {
  for (const [status, label] of [['known_verified', 'VERIFIED'], ['likely_inferred', 'LIKELY / INFERRED'], ['unknown', 'UNKNOWN']]) {
    const data = { ...highIntelligence, data_origin: 'demo', attribution: { ...highIntelligence.attribution, attribution_status: status, entity_name: status === 'unknown' ? null : '<img src=x onerror=alert(1)>' } };
    const html = renderToStaticMarkup(React.createElement(DestinationIntelligencePanel, { data, onSelect: noop }));
    assert.ok(html.includes(label) && html.includes('DEMO DATA'));
    assert.ok(!html.includes('<img'));
    if (status === 'likely_inferred') assert.ok(!html.includes('>VERIFIED<'));
  }
});

function buttonsIn(element) {
  if (!element || typeof element !== 'object') return [];
  if (Array.isArray(element)) return element.flatMap(buttonsIn);
  if (typeof element.type === 'function') return buttonsIn(element.type(element.props));
  return [...(element.type === 'button' ? [element] : []), ...buttonsIn(element.props?.children)];
}

test('Copilot retains each of 62 actual event links and invokes the existing selection callback', () => {
  const selected = [];
  const records = observedGraph.edges.map(e => ({ kind: 'transfer', id: e.id, label: e.amount_exact, source: 'alchemy_ethereum' }));
  const answer = { answer: 'Observed records', sections: [{ title: 'Observed records', items: ['62 transfer events'] }], supporting_records: records, sources: ['persisted_case_run'], limitations: ['Partial observation'], data_origin: 'observed', attribution_status: 'unknown', run_id: observedGraph.run_id, coverage: highActivity.capability.coverage, next_review_step: 'Review transfer evidence and coverage' };
  const props = { answer, question: 'Supporting transfers', input: '', loading: false, disabled: false, contextLabel: 'Current case', onInput: noop, onAsk: noop, onSelect: r => selected.push(r.id) };
  const element = React.createElement(CopilotPanel, props);
  const html = renderToStaticMarkup(element);
  for (const label of ['Answer', 'Key evidence (0)', 'Supporting transfers (62)', 'Next review step', 'Sources &amp; limitations', 'PARTIAL']) assert.ok(html.includes(label));
  for (const button of buttonsIn(element).filter(b => b.props.title && records.some(r => r.id === b.props.title))) button.props.onClick();
  assert.deepEqual(new Set(selected), new Set(records.map(r => r.id)));
});

test('action readiness distinguishes local package preparation from real external action', () => {
  const shared = { evidenceCount: 62, transferCount: 4, candidate: observedGraph.destination.address, attribution: 'unknown', dataOrigin: 'observed', onEvidence: noop, onAudit: noop };
  const html = renderToStaticMarkup(React.createElement(ActionReadinessSummary, { ...shared, ready: false, isDemo: false }));
  for (const text of ['REQUIRED', 'NOT READY', 'external action unavailable', 'View evidence', 'View audit']) assert.ok(html.includes(text));
  assert.ok(!html.includes('Freeze Wallet'));
  const demo = renderToStaticMarkup(React.createElement(ActionReadinessSummary, { ...shared, ready: true, isDemo: true, dataOrigin: 'demo' }));
  assert.ok(demo.includes('DEMO DATA') && demo.includes('READY FOR LOCAL PREPARATION'));
  const unavailable = renderToStaticMarkup(React.createElement(ActionReadinessSummary, { ...shared, ready: false, isDemo: false, dataOrigin: 'none', evidenceCount: 0, transferCount: 0, candidate: null }));
  assert.ok(unavailable.includes('NO OBSERVED DATA') && !unavailable.includes('PROVIDER-OBSERVED DATA'));
});

test('all 62 captured addresses fit inside the initial 3D viewport', () => {
  const html = renderToStaticMarkup(React.createElement(Network3D, { graph: observedGraph, path: selectedPath(observedGraph, null), isolate: false, selection: null, focus: 0, onWallet: noop, onTransfer: noop }));
  const points = [...html.matchAll(/transform="translate\(([-\d.]+) ([-\d.]+)\)" class="trail-svg-node"/g)];
  assert.equal(points.length, highActivity.summary.nodes);
  for (const [, x, y] of points) { assert.ok(Math.abs(Number(x)) < 450, 'wallet outside horizontal viewport'); assert.ok(Math.abs(Number(y)) < 265, 'wallet outside vertical viewport'); }
});

test('captured high-activity coverage names the stop reason and request count', () => {
  const html = renderToStaticMarkup(React.createElement(CoverageStrip, { capability: highActivity.capability }));
  for (const value of ['PARTIAL', 'TIMEOUT', '29 provider requests', '20000047', '20000355', highActivity.capability.run_id]) assert.ok(html.includes(value));
  assert.ok(!html.includes('Yes, within observation boundaries'));
});

test('high-activity views retain every observed wallet and event with independent selection', () => {
  const before = JSON.stringify(observedGraph);
  assert.equal(observedGraph.nodes.length, 62);
  assert.equal(observedGraph.edges.length, 62);
  assert.equal(new Set(observedGraph.edges.map(edge => edge.hash)).size, 4);
  const layout = layoutGraph(observedGraph);
  assert.equal(layout.length, observedGraph.nodes.length);
  layout.forEach((item, index) => assert.equal(item.node, observedGraph.nodes[index]));
  const html = renderToStaticMarkup(React.createElement(Network3D, { graph: observedGraph, path: selectedPath(observedGraph, null), isolate: false, selection: null, focus: 0, onWallet: noop, onTransfer: noop }));
  assert.equal((html.match(/class="trail-svg-edge"/g) || []).length, observedGraph.edges.length);
  assert.equal((html.match(/class="trail-svg-node"/g) || []).length, observedGraph.nodes.length);
  for (const edge of observedGraph.edges) {
    const selection = { wallets: [edge.source, edge.target], transfers: [edge.id], label: 'Observed event' };
    const path = selectedPath(observedGraph, selection);
    assert.deepEqual([...path.transfers], [edge.id]);
    const isolated = renderToStaticMarkup(React.createElement(Network3D, { graph: observedGraph, path, isolate: true, selection, focus: 1, onWallet: noop, onTransfer: noop }));
    assert.equal((isolated.match(/class="trail-svg-edge"/g) || []).length, 1);
    assert.equal((isolated.match(/class="trail-svg-node"/g) || []).length, path.wallets.size);
  }
  assert.equal(JSON.stringify(observedGraph), before);
});

test('captured high-activity transfer and wallet inspectors keep actual values and partial coverage', () => {
  for (const transfer of highActivity.transactions) {
    const html = renderToStaticMarkup(React.createElement(TransferInspector, { transfer, network: 'ethereum', capability: highActivity.capability, canSave: false, saving: false, message: '', onSave: noop, onClose: noop, onWallet: noop, onFocus: noop }));
    assert.ok(html.includes(transfer.amount_base_units));
    assert.ok(html.includes(transfer.amount_exact));
    assert.ok(html.includes(transfer.hash));
    assert.ok(html.includes('PARTIAL'));
  }
  for (const wallet of observedGraph.nodes) {
    const html = renderToStaticMarkup(React.createElement(WalletInspector, { wallet, network: 'Ethereum Mainnet', onClose: noop, onTransfers: noop, onEvidence: noop, onWhy: noop, onFocus: noop }));
    assert.ok(html.includes(wallet.address));
    assert.ok(html.includes('UNKNOWN'));
    assert.ok(!html.includes('VERIFIED'));
  }
});
