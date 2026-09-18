import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { walletError, reporterStatus, reporterError, formatReportDate, networkOptions } from './reporter-ui.ts';

const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../app/reporter/page.tsx', import.meta.url), 'utf8');
const ast = ts.createSourceFile('page.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const stateNames = [];
const page = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'ReporterPage');
function collect(node) {
  if (ts.isVariableDeclaration(node) && ts.isArrayBindingPattern(node.name) && node.initializer
    && ts.isCallExpression(node.initializer) && node.initializer.expression.getText(ast) === 'useState') {
    stateNames.push(node.name.elements[0].name.getText(ast));
  }
  ts.forEachChild(node, collect);
}
collect(page);
const compiled = ts.transpileModule(source, { compilerOptions: {
  jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText;

// Isolated component fixtures only; no test data is sent to a service or included in the app.
const report = { id: 'test-id', reference_number: 'CTR-TEST-REFERENCE', title: 'Test report',
  reported_wallet: '0x' + 'a'.repeat(40), blockchain: 'ethereum', asset: 'ETH', status: 'report_received',
  submitted_at: '2026-01-01T12:00:00Z', last_status_update: '2026-01-02T12:00:00Z',
  capability: { data_origin: 'none', provider_state: 'not_connected' } };

function reporter(overrides = {}, apiOverrides = {}) {
  const state = { user: { role: 'reporter' }, ready: true, loading: false, ...overrides };
  const refs = [];
  const effects = [];
  const routes = [];
  let cursor = 0;
  let refCursor = 0;
  let insidePage = false;
  class ApiError extends Error { constructor(status) { super('PRIVATE DATABASE ERROR'); this.status = status; } }
  const api = { listReporterSubmissions: async () => [], ...apiOverrides };
  const compiledModule = { exports: {} };
  const load = name => {
    if (name === 'react') return { ...React,
      useState: initial => {
        if (!insidePage) return [initial, () => {}];
        const key = stateNames[cursor++];
        if (!(key in state)) state[key] = typeof initial === 'function' ? initial() : initial;
        return [state[key], next => { state[key] = typeof next === 'function' ? next(state[key]) : next; }];
      },
      useRef: current => refs[refCursor++] ||= { current }, useEffect: fn => effects.push(fn), useCallback: fn => fn,
    };
    if (name.endsWith('.css')) return {};
    if (name === 'next/navigation') return { useRouter: () => ({ replace: route => routes.push(route) }) };
    if (name === '@/lib/api') return { default: api, ApiError };
    if (name === '@/lib/reporter-ui') return require('./reporter-ui.ts');
    return require(name);
  };
  new Function('require', 'module', 'exports', compiled)(load, compiledModule, compiledModule.exports);
  function render() {
    cursor = 0; refCursor = 0; insidePage = true;
    try { return compiledModule.exports.default(); } finally { insidePage = false; }
  }
  return { state, render, html: () => renderToStaticMarkup(render()), ApiError, effects, routes };
}

function find(tree, predicate) {
  if (!React.isValidElement(tree)) return undefined;
  if (predicate(tree)) return tree;
  for (const child of React.Children.toArray(tree.props.children)) {
    const match = find(child, predicate);
    if (match) return match;
  }
}

test('wallet feedback follows the existing backend formats for every supported network', () => {
  const examples = { demo: '0xReported001', ethereum: '0x' + 'a'.repeat(40), polygon: '0x' + 'A'.repeat(40),
    bsc: '0x' + '1'.repeat(40), tron: 'T' + 'A'.repeat(33), bitcoin: 'bc1' + 'a'.repeat(20) };
  for (const network of networkOptions) {
    assert.equal(walletError(` ${examples[network.value]} `, network.value), undefined);
    assert.ok(walletError('', network.value));
    assert.ok(walletError('bad-address', network.value));
  }
  assert.ok(walletError('0x' + 'g'.repeat(40), 'ethereum'));
  assert.ok(walletError('0x' + 'a'.repeat(39), 'ethereum'));
  assert.ok(walletError('0x' + 'a'.repeat(254), 'demo'));
});

test('all actual backend statuses have safe copy and unknown states are unavailable', () => {
  const backend = readFileSync(new URL('../../backend/app/api/reporter.py', import.meta.url), 'utf8');
  const statusFunction = backend.split('def _reporter_status(')[1].split('async def _serialize_submission')[0];
  const statuses = [...statusFunction.matchAll(/return\s*\(\s*"([a-z_]+)"/g)].map(match => match[1]);
  assert.equal(statuses.length, 6);
  for (const status of statuses) {
    assert.notEqual(reporterStatus(status).label, 'Status unavailable');
    const html = reporter({ view: 'track', submissions: [{ ...report, status }] }).html();
    assert.match(html, /aria-current="step"/);
    assert.match(html, /Last update/);
    assert.doesNotMatch(html, /provider|database|recovery guaranteed/i);
    assert.equal((html.match(/class="rp-step/g) || []).length, status === 'report_received' ? 1 : 2);
  }
  assert.equal(reporterStatus('investigation_completed').label, 'Status unavailable');
  assert.match(reporterStatus('case_closed').description, /does not confirm recovery/);
  assert.match(reporterStatus('analysis_completed').description, /remains open/);
  assert.equal(formatReportDate('bad-date'), null);
  assert.equal(formatReportDate(), null);
});

test('entry, form, success and tracking expose the existing reporter flow', () => {
  assert.match(reporter().html(), /Report Suspicious Wallet/);
  assert.match(reporter().html(), /Track My Report/);
  const form = reporter({ view: 'report' }).html();
  assert.match(form, /Required/); assert.match(form, /Optional/); assert.match(form, /DEMO DATA/);
  assert.match(form, /id="report-wallet"[^>]*>0xReported001<\/textarea>/);
  assert.doesNotMatch(form, /CapabilityNotice|provider/i);
  const success = reporter({ view: 'success', created: report }).html();
  assert.match(success, /CTR-TEST-REFERENCE/); assert.match(success, /Copy reference ID/); assert.match(success, /Track Report/);
});

test('tracking distinguishes empty, not found, loading and failed requests without stale results', () => {
  assert.match(reporter({ view: 'track' }).html(), /No reports yet/);
  assert.match(reporter({ view: 'track', submissions: [report], referenceQuery: 'MISSING' }).html(), /Report not found/);
  assert.match(reporter({ view: 'track', loading: true }).html(), /Checking your reports/);
  const unavailable = reporter({ view: 'track', loadError: reporterError(undefined, 'load'), submissions: [report] }).html();
  assert.match(unavailable, /Reports are unavailable/); assert.doesNotMatch(unavailable, /CTR-TEST-REFERENCE/);
  assert.match(reporterError(401, 'submit'), /sign in again/);
  assert.match(reporterError(422, 'submit'), /Check the wallet address/);
});

test('validation prevents requests and simultaneous submits issue only one request', async () => {
  let calls = 0;
  let resolve;
  const ui = reporter({ view: 'report', blockchain: 'ethereum' }, {
    createReporterSubmission: () => { calls++; return new Promise(done => { resolve = done; }); },
  });
  const submit = () => find(ui.render(), node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await submit();
  assert.equal(calls, 0); assert.ok(ui.state.fieldErrors.wallet);
  ui.state.wallet = report.reported_wallet;
  const first = submit();
  await submit();
  assert.equal(calls, 1); assert.equal(ui.state.submitting, true);
  resolve(report); await first;
  assert.equal(ui.state.view, 'success'); assert.equal(ui.state.created.reference_number, report.reference_number);
  assert.equal(ui.state.submitting, false);
  assert.equal(ui.state.submissions.length, 1);
});

test('submission errors preserve the draft and never render raw errors', async () => {
  const ui = reporter({ view: 'report', wallet: '0xReported001', description: 'Keep this draft' }, {
    createReporterSubmission: async () => { throw new Error('PRIVATE DATABASE ERROR'); },
  });
  await find(ui.render(), node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  assert.equal(ui.state.description, 'Keep this draft'); assert.equal(ui.state.submitting, false);
  assert.match(ui.html(), /Check your reports before submitting again/);
  assert.doesNotMatch(ui.html(), /PRIVATE DATABASE ERROR/);
});

test('direct reporter entry with no session or a staff session stays on reporter sign in', () => {
  const original = globalThis.window;
  globalThis.window = { scrollTo() {} };
  try {
    for (const [token, role] of [[null, 'reporter'], ['staff-session', 'investigator'], ['staff-session', 'admin']]) {
      const ui = reporter({ user: { role }, ready: false }, {
        getToken: () => token,
        listReporterSubmissions: () => assert.fail('Do not load reports for this session'),
      });
      ui.render(); ui.effects[0]();
      assert.deepEqual(ui.routes, ['/#reporter']);
      assert.doesNotMatch(ui.html(), /Reporter navigation|Report Suspicious Wallet/);
    }
  } finally { globalThis.window = original; }
});
