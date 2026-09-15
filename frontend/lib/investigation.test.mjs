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
  const module = { exports: {} };
  const load = path => path.startsWith('@/lib/') ? require(`./${path.slice(6)}.ts`) : require(path);
  new Function('require', 'module', 'exports', output)(load, module, module.exports);
  return module.exports;
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
