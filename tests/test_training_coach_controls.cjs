const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

class Element {
    constructor(tag = 'div') {this.tag = tag; this.children = []; this.textContent = ''; this.attributes = {};
        Object.defineProperty(this, 'dataset', {value: {}, writable: false});}
    append(...items) {this.children.push(...items);}
    replaceChildren(...items) {this.children = items; this.textContent = '';}
    setAttribute(key, value) {this.attributes[key] = value;}
    set innerHTML(value) {this.html = value; this.lastElementChild = new Element('td');}
}
function load(extra = {}, file = 'model-training-coach.js') {
    const controls = Object.fromEntries(['trainingCoachTitle', 'trainingCoachBody', 'trainingCoachModal'].map(id => [id, new Element()]));
    const context = vm.createContext({document: {getElementById: id => controls[id], createElement: tag => new Element(tag)},
        bootstrap: {Modal: {getOrCreateInstance: () => ({show() {}})}}, ...extra});
    const source = fs.readFileSync('app/dashboard/js/components/' + file, 'utf8').replace(/^import[\s\S]*?;/gm, '').replace(/export /g, '');
    vm.runInContext(source, context);
    return {context, controls};
}
function nodes(node) {return [node, ...node.children.flatMap(nodes)];}
function text(node) {return nodes(node).map(item => item.textContent).join('\n');}
function button(body, action) {return nodes(body).find(item => item.dataset.action === action);}
const params = {feature_set_id: 'core-v1', n_estimators: 100, max_depth: 3, learning_rate: .05};
const report = {coach_id: 'coach-1', source: 'local_evidence', source_note: 'AI is not configured.',
    summary: 'Investigate the measured tradeoffs.', findings: ['No positive predictions at the decision threshold.'],
    reasoning: ['Review both directions.'], caveats: ['Fresh validation is needed.'],
    evidence: {market_context: {symbol: 'XAUUSD', timeframe: 'M5', data_source: 'yahoo'},
        label_definition_id: 'future_return_up-n12-t0.003', probability_threshold: .5},
    plan: {fresh_after: '2026-01-02T00:00:00Z', variants: [{id: 'current-recipe', parameters: params, rationale: 'Reference'}]},
    can_validate: true, history_saved: true, validation_history: [],
    tracking: [{model_id: 'm', recipe: 'current-recipe', initial_beats_baseline: true,
        fresh_periods: 2, fresh_periods_beating_baseline: 1, status: 'mixed_or_worse'}]};
const waiting = {status: 'waiting_for_fresh_data', samples: 12, required_samples: 50,
    fresh_after: '2026-01-02T00:00:00Z', notes: ['Earlier periods are not reused.']};

test('each model offers its own Coach and both pages contain exactly one coach dialog', () => {
    const selected = [];
    const {context} = load({openTrainingCoach: model => selected.push(model.model_id)}, 'model-operations.js');
    for (const status of ['candidate', 'champion', 'retired']) {
        context.model = {model_id: status, status, metrics: {}};
        const row = vm.runInContext('row(model,{})', context);
        row.lastElementChild.children.find(item => item.textContent === 'Coach').onclick();
    }
    assert.deepEqual(selected, ['candidate', 'champion', 'retired']);
    for (const file of ['index.html', 'ai-model-lab.html']) {
        const html = fs.readFileSync('app/dashboard/' + file, 'utf8');
        for (const id of ['trainingCoachModal', 'trainingCoachTitle', 'trainingCoachBody']) assert.equal(html.split('id="' + id + '"').length - 1, 1);
    }
});

test('opening reviews evidence without automatically running tests and preserves read-only DOM dataset', async () => {
    const calls = [];
    const {context, controls} = load({reviewTrainingCoach: async id => {calls.push(['review', id]); return report;},
        runTrainingCoach: async () => {throw new Error('must not train');}});
    await vm.runInContext('openTrainingCoach({model_id:"selected"})', context);
    assert.deepEqual(calls, [['review', 'selected']]);
    const body = controls.trainingCoachBody;
    assert.match(text(body), /Local evidence coach/);
    assert.match(text(body), /AI is not configured/);
    assert.match(text(body), /No positive predictions/);
    assert.match(text(body), /Mixed or worse/);
    assert.doesNotMatch(text(body), /undefined|NaN/);
    assert.equal(button(body, 'run').disabled, false);
});

test('recommended test click sends only the selected model and saved coach id; waiting is explicit', async () => {
    const sent = [];
    const {context, controls} = load({reviewTrainingCoach: async () => report,
        runTrainingCoach: async (...args) => {sent.push(args); return waiting;}});
    await vm.runInContext('openTrainingCoach({model_id:"selected"})', context);
    await button(controls.trainingCoachBody, 'run').onclick();
    assert.deepEqual(sent, [['selected', 'coach-1']]);
    assert.match(text(controls.trainingCoachBody), /12 of 50 required/);
    assert.match(text(controls.trainingCoachBody), /Earlier periods are not reused/);
    assert.equal(button(controls.trainingCoachBody, 'run').disabled, false);
});

test('fresh validation never calls training and failures remain retryable', async () => {
    const calls = [];
    const {context, controls} = load({reviewTrainingCoach: async () => report,
        validateTrainingCoach: async id => {calls.push(id); throw new Error('source offline');},
        runTrainingCoach: async () => {throw new Error('must not train');}});
    await vm.runInContext('openTrainingCoach({model_id:"selected"})', context);
    await button(controls.trainingCoachBody, 'validate').onclick();
    assert.deepEqual(calls, ['selected']);
    assert.match(text(controls.trainingCoachBody), /Coach action failed: source offline.*retry/);
    assert.equal(button(controls.trainingCoachBody, 'validate').disabled, false);
});

test('missing bootstrap and unsaved review disable their actions, including after refresh', async () => {
    const limited = {...report, can_validate: false, history_saved: false, tracking: []};
    const {context, controls} = load({reviewTrainingCoach: async () => limited});
    await vm.runInContext('openTrainingCoach({model_id:"selected"})', context);
    assert.equal(button(controls.trainingCoachBody, 'run').disabled, true);
    assert.equal(button(controls.trainingCoachBody, 'validate').disabled, true);
    await button(controls.trainingCoachBody, 'review').onclick();
    assert.equal(button(controls.trainingCoachBody, 'run').disabled, true);
    assert.equal(button(controls.trainingCoachBody, 'validate').disabled, true);
});

test('double clicks do not duplicate jobs and late reviews cannot overwrite a newly selected model', async () => {
    let finish, count = 0;
    const {context, controls} = load({reviewTrainingCoach: async () => report,
        runTrainingCoach: () => {count++; return new Promise(resolve => {finish = resolve;});}});
    await vm.runInContext('openTrainingCoach({model_id:"selected"})', context);
    const run = button(controls.trainingCoachBody, 'run');
    const first = run.onclick(); await run.onclick();
    assert.equal(count, 1); assert.equal(run.disabled, true);
    finish(waiting); await first;
    const requests = [];
    const stale = load({reviewTrainingCoach: id => new Promise(resolve => requests.push({id, resolve}))});
    const old = vm.runInContext('openTrainingCoach({model_id:"old"})', stale.context);
    const current = vm.runInContext('openTrainingCoach({model_id:"current"})', stale.context);
    requests[1].resolve({...report, summary: 'Current review'}); await current;
    requests[0].resolve({...report, summary: 'Old review'}); await old;
    assert.match(text(stale.controls.trainingCoachBody), /Current review/);
    assert.doesNotMatch(text(stale.controls.trainingCoachBody), /Old review/);
});

test('fresh results render missing AUC, negative skill and failed artifacts as safe text', () => {
    const {context, controls} = load();
    const score = {roc_auc: null, brier_skill: -.2, beats_baseline: false};
    context.report = {status: 'partial', samples: 90, evaluation_start: 'start', evaluation_end: 'end',
        results: [{recipe: 'current-recipe', status: 'completed', scores: {up: score, down: score}},
                  {recipe: 'feature-check', status: 'failed', error: '<script>bad</script>'}],
        history_saved: true, notes: ['Baseline is frozen.']};
    vm.runInContext('renderFreshValidation(document.getElementById("trainingCoachBody"),report)', context);
    const body = controls.trainingCoachBody;
    assert.match(text(body), /without retraining/);
    assert.match(text(body), /Unavailable/);
    assert.match(text(body), /-0\.2000/);
    assert.match(text(body), /<script>bad<\/script>/);
    assert.ok(nodes(body).every(item => item.html === undefined));
});
