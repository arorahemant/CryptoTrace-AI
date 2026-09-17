import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// Exercise the actual page JSX and its layout handlers without API calls or a browser dependency.
const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../app/investigate/page.tsx', import.meta.url), 'utf8');
const ast = ts.createSourceFile('page.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const stateNames = [];
function collectStates(node) {
  if (ts.isVariableDeclaration(node) && ts.isArrayBindingPattern(node.name)
    && node.initializer && ts.isCallExpression(node.initializer)
    && node.initializer.expression.getText(ast) === 'useState') {
    stateNames.push(node.name.elements[0].name.getText(ast));
  }
  ts.forEachChild(node, collectStates);
}
collectStates(ast);
const compiled = ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const capture = JSON.parse(readFileSync(new URL('../../backend/tests/fixtures/high_activity_alchemy.json', import.meta.url)));

function workspace(overrides = {}, withGraph = true) {
  const state = {
    caseData: { case_number: 'UI-TEST', blockchain: 'ethereum', status: 'investigating', lifecycle: 'open',
      reported_wallet: capture.graph.nodes[0].address, permissions: [], capability: capture.capability },
    investigation: withGraph ? { graph: capture.graph, stats: {}, risk: { overall: 'unassessed' } } : null,
    loading: false, ...overrides,
  };
  let cursor = 0;
  const compiledModule = { exports: {} };
  const load = name => {
    if (name === 'react') return { ...React,
      useState: initial => {
        const key = stateNames[cursor++];
        if (!(key in state)) state[key] = initial;
        return [state[key], next => { state[key] = typeof next === 'function' ? next(state[key]) : next; }];
      },
      useEffect: () => {}, useMemo: fn => fn(), useCallback: fn => fn, useRef: current => ({ current }),
    };
    if (name.endsWith('.css') || name === '@/lib/api') return {};
    if (name === 'next/navigation') return { useRouter: () => ({}), useSearchParams: () => new URLSearchParams('caseId=ui-test') };
    if (name.startsWith('@/components/')) return new Proxy({}, { get: (_, component) =>
      props => React.createElement('div', { 'data-component': component, 'data-run-id': props.graph?.run_id }) });
    if (name.startsWith('@/lib/')) return require(`./${name.slice(6)}.ts`);
    return require(name);
  };
  new Function('require', 'module', 'exports', compiled + '\nexports.renderWorkspace = InvestigateContent;')(load, compiledModule, compiledModule.exports);
  const render = () => { cursor = 0; return compiledModule.exports.renderWorkspace(); };
  return { render, state };
}

function controls(tree) {
  // Requiring a direct child guarantees that hidden panels and graph branches cannot hide it.
  const row = React.Children.toArray(tree.props.children).find(child => child.props?.['aria-label'] === 'Workspace layout');
  assert.ok(row, 'layout controls must be a direct child of the workspace shell');
  assert.ok(!row.props.hidden);
  const buttons = React.Children.toArray(row.props.children);
  assert.equal(buttons.length, 4);
  for (const button of buttons) {
    assert.equal(button.type, 'button');
    assert.ok(!button.props.hidden && !button.props.disabled);
  }
  return { row, buttons, html: renderToStaticMarkup(row) };
}

test('all layout controls render with and without graph results, including focus mode', () => {
  for (const withGraph of [false, true]) {
    for (const graphFocus of [false, true]) {
      for (const expanded of [false, true]) {
        const { render } = workspace({ graphFocus, summaryExpanded: expanded, sidebarCollapsed: !expanded,
          inspectorOpen: expanded, focusInspectorOpen: expanded }, withGraph);
        const { html } = controls(render());
        assert.match(html, /Case Summary: (Expand|Collapse)/);
        assert.match(html, /(Expand|Collapse) Sidebar/);
        assert.match(html, /(Open|Collapse) Inspector/);
        assert.match(html, graphFocus ? /Exit Focus \(Esc\)/ : /Graph Focus/);
      }
    }
  }
});

test('persistent buttons expand/collapse panels and enter/exit focus using the page handlers', () => {
  const { render, state } = workspace();
  for (const index of [0, 1, 2]) controls(render()).buttons[index].props.onClick();
  assert.equal(state.sidebarCollapsed, false);
  assert.equal(state.summaryExpanded, true);
  assert.equal(state.inspectorOpen, true);
  for (const index of [0, 1, 2]) controls(render()).buttons[index].props.onClick();
  assert.equal(state.sidebarCollapsed, true);
  assert.equal(state.summaryExpanded, false);
  assert.equal(state.inspectorOpen, false);
  controls(render()).buttons[3].props.onClick();
  assert.equal(state.graphFocus, true);
  controls(render()).buttons[2].props.onClick();
  assert.equal(state.focusInspectorOpen, true);
  controls(render()).buttons[3].props.onClick();
  assert.equal(state.graphFocus, false);
  assert.equal(state.focusInspectorOpen, false);
});

test('opening summary or sidebar from focus reveals the requested panel', () => {
  for (const index of [0, 1]) {
    const { render, state } = workspace({ graphFocus: true });
    controls(render()).buttons[index].props.onClick();
    assert.equal(state.graphFocus, false);
    assert.equal(index === 0 ? !state.sidebarCollapsed : state.summaryExpanded, true);
  }
});
