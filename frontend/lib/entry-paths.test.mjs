import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText;

function login(path, { demo = true, role = path, fail = false, deferred = false } = {}) {
  const state = [];
  const refs = [];
  const effects = [];
  const routes = [];
  const requests = [];
  let cursor = 0;
  let refCursor = 0;
  let cleared = 0;
  let resolve;
  const api = { login: async (...args) => {
    requests.push(args);
    if (fail) throw new Error('PRIVATE SERVER ERROR');
    if (deferred) await new Promise(done => { resolve = done; });
    return { user: { role } };
  }, clearToken: () => { cleared++; } };
  const compiledModule = { exports: {} };
  const load = name => {
    if (name === 'react') return { ...React,
      useState: initial => { const index = cursor++; if (!(index in state)) state[index] = initial; return [state[index], value => { state[index] = value; }]; },
      useRef: current => refs[refCursor++] ||= { current },
      useEffect: fn => { effects.push(fn); },
    };
    if (name === 'next/navigation') return { useRouter: () => ({ push: route => routes.push(route) }) };
    if (name === 'next/link') return { default: props => React.createElement('a', props) };
    if (name === '@/lib/api') return { default: api };
    return require(name);
  };
  new Function('require', 'module', 'exports', compiled + '\nexports.PathLogin = PathLogin;')(load, compiledModule, compiledModule.exports);
  function render(entry = false) {
    cursor = 0; refCursor = 0;
    return entry ? compiledModule.exports.default() : compiledModule.exports.PathLogin({ path, demoAvailable: demo });
  }
  return { render, state, routes, requests, effects, resolve: () => resolve(), cleared: () => cleared };
}

function find(tree, predicate) {
  if (!React.isValidElement(tree)) return;
  if (predicate(tree)) return tree;
  for (const child of React.Children.toArray(tree.props.children)) {
    const match = find(child, predicate);
    if (match) return match;
  }
}
const submit = ui => find(ui.render(), node => node.type === 'form').props.onSubmit({ preventDefault() {} });

test('entry offers two explicit paths without a mixed login form', () => {
  const ui = login('reporter');
  const html = renderToStaticMarkup(ui.render(true));
  assert.match(html, />INVESTIGATOR</); assert.match(html, />REPORTER</);
  assert.match(html, /href="#investigator"/); assert.match(html, /href="\/reporter"/);
  assert.doesNotMatch(html, /<form|type="password"/);
});

test('reporter is prefilled from its existing seed even before capability availability resolves', () => {
  for (const demo of [true, false]) {
    const ui = login('reporter', { demo });
    const tree = ui.render();
    assert.equal(find(tree, node => node.props.id === 'username').props.value, 'reporter');
    assert.equal(find(tree, node => node.props.id === 'password').props.value, 'report123');
  }
});

test('investigator prefill behavior remains unchanged', () => {
  const demo = login('investigator').render();
  assert.equal(find(demo, node => node.props.id === 'username').props.value, 'investigator');
  assert.equal(find(demo, node => node.props.id === 'password').props.value, 'investigate123');
  const production = login('investigator', { demo: false }).render();
  assert.equal(find(production, node => node.props.id === 'username').props.value, '');
  assert.equal(find(production, node => node.props.id === 'password').props.value, '');
});

test('demo account labels match the selected path', () => {
  for (const path of ['reporter', 'investigator']) {
    const ui = login(path);
    const tree = ui.render();
    const html = renderToStaticMarkup(tree);
    assert.match(html, new RegExp(`DEMO ${path.toUpperCase()} ACCOUNT`));
    if (path === 'reporter') assert.doesNotMatch(html, /investigator|dashboard|cases|graph|evidence/i);
  }
});

test('matching roles navigate only to their selected workspace through the existing API', async () => {
  const original = globalThis.localStorage;
  const saved = [];
  globalThis.localStorage = { setItem: (...args) => saved.push(args), removeItem() {} };
  try {
    for (const role of ['reporter', 'investigator', 'supervisor', 'admin']) {
      const path = role === 'reporter' ? 'reporter' : 'investigator';
      const ui = login(path, { role });
      await submit(ui);
      assert.deepEqual(ui.routes, [path === 'reporter' ? '/reporter' : '/dashboard']);
      assert.equal(ui.requests.length, 1);
      assert.equal(JSON.parse(saved.at(-1)[1]).role, role);
    }
  } finally { globalThis.localStorage = original; }
});

test('wrong-path or unknown roles never navigate and clear the mismatched session', async () => {
  const original = globalThis.localStorage;
  globalThis.localStorage = { setItem() { assert.fail('Wrong-path identity must not be saved'); }, removeItem() {} };
  try {
    for (const [path, role] of [['reporter', 'investigator'], ['reporter', 'admin'], ['investigator', 'reporter'], ['investigator', 'unknown']]) {
      const ui = login(path, { role });
      await submit(ui);
      assert.deepEqual(ui.routes, []); assert.equal(ui.cleared(), 1);
      assert.match(renderToStaticMarkup(ui.render()), /This account cannot open/);
    }
  } finally { globalThis.localStorage = original; }
});

test('failed sign in is safe and an abandoned request cannot open another path', async () => {
  const failed = login('reporter', { fail: true });
  await submit(failed);
  assert.deepEqual(failed.routes, []);
  assert.doesNotMatch(renderToStaticMarkup(failed.render()), /PRIVATE SERVER ERROR/);
  const original = globalThis.localStorage;
  globalThis.localStorage = { removeItem() {} };
  try {
    const ui = login('reporter', { deferred: true });
    ui.render();
    const cleanup = ui.effects[0]();
    const request = submit(ui);
    await submit(ui);
    assert.equal(ui.requests.length, 1);
    cleanup(); ui.resolve(); await request;
    assert.deepEqual(ui.routes, []);
  } finally { globalThis.localStorage = original; }
});
