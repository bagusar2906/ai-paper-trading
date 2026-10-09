const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

class Element {
    constructor(tag = 'div') {this.tag = tag; this.children = []; this.textContent = ''; this.attributes = {};}
    append(...nodes) {this.children.push(...nodes);}
    replaceChildren(...nodes) {this.children = nodes; this.textContent = '';}
    setAttribute(key, value) {this.attributes[key] = value;}
    set innerHTML(value) {this.html = value; this.lastElementChild = new Element('td');}
}
function load(extra = {}, file = 'model-experiments.js') {
    const controls = Object.fromEntries(['modelExperimentsTitle', 'modelExperimentsBody', 'modelExperimentsModal'].map(id => [id, new Element()]));
    const context = vm.createContext({document: {getElementById: id => controls[id], createElement: tag => new Element(tag)},
        bootstrap: {Modal: {getOrCreateInstance: () => ({show() {}})}}, ...extra});
    const source = fs.readFileSync('app/dashboard/js/components/' + file, 'utf8').replace(/^import[\s\S]*?;/gm, '').replace(/export /g, '');
    vm.runInContext(source, context);
    return {context, controls};
}
function nodes(node) {return [node, ...node.children.flatMap(nodes)];}
function text(node) {return nodes(node).map(item => item.textContent).join('\n');}
const parameters = {symbol: 'XAUUSD', timeframe: 'M5', data_source: 'yahoo', bars: 5000,
    feature_set_id: 'raw-ohlcv-v1', probability_threshold: .5, n_estimators: 100, max_depth: 3, learning_rate: .05};
const plan = {parameters, variants: [{id: 'current-recipe', parameters, rationale: 'Reference'}],
    notes: ['Same unseen timestamps'], holdout_fraction: .2};
const scores = {roc_auc: null, brier_score: .1, log_loss: .3, brier_skill: -.1, precision: 0, recall: 0,
    positive_predictions: 0, beats_baseline: false};
const baseline = {probability: .1, observed_rate: .12, scores};
const report = {status: 'completed', samples: 100, evaluation_start: '2026-01-03', evaluation_end: '2026-01-04',
    training_rows: 500, training_end: '2026-01-02', purge_candles: 12, baseline: {up: baseline, down: baseline},
    results: [{recipe: 'current-recipe', model_id: '<script>bad</script>', status: 'completed', parameters, scores: {up: scores, down: scores}},
              {recipe: 'feature-check', status: 'failed', error: 'source offline'}],
    history_saved: true, notes: ['Use fresh future data before promotion']};

test('each model opens its own experiment plan and both dashboards have one dialog', () => {
    const chosen = [];
    const {context} = load({openModelExperiments: model => chosen.push(model.model_id)}, 'model-operations.js');
    for (const status of ['candidate', 'champion', 'retired']) {
        context.model = {model_id: status, status, metrics: {}};
        const row = vm.runInContext('row(model,{})', context);
        row.lastElementChild.children.find(node => node.textContent === 'Experiments').onclick();
    }
    assert.deepEqual(chosen, ['candidate', 'champion', 'retired']);
    for (const file of ['index.html', 'ai-model-lab.html']) {
        const html = fs.readFileSync('app/dashboard/' + file, 'utf8');
        for (const id of ['modelExperimentsModal', 'modelExperimentsTitle', 'modelExperimentsBody']) assert.equal(html.split('id="' + id + '"').length - 1, 1);
    }
});

test('opening previews recipes without starting training; explicit click runs and displays results', async () => {
    const calls = [];
    const {context, controls} = load({getControlledExperimentPlan: async () => plan, getModelReviewHistory: async () => [],
        runControlledExperiments: async id => {calls.push(id); return report;}});
    await vm.runInContext('openModelExperiments({model_id:"selected"})', context);
    assert.equal(calls.length, 0);
    assert.match(text(controls.modelExperimentsBody), /Same unseen timestamps/);
    const button = nodes(controls.modelExperimentsBody).find(node => node.tag === 'button');
    await button.onclick();
    assert.deepEqual(calls, ['selected']);
    assert.equal(button.disabled, false);
    assert.match(text(controls.modelExperimentsBody), /Brier skill/);
    assert.match(text(controls.modelExperimentsBody), /UP .*Historical-rate baseline/);
    assert.match(text(controls.modelExperimentsBody), /DOWN .*Historical-rate baseline/);
    assert.match(text(controls.modelExperimentsBody), /Needs improvement/);
    assert.match(text(controls.modelExperimentsBody), /Alternative features failed: source offline/);
    assert.match(text(controls.modelExperimentsBody), /Unavailable/);
    assert.ok(nodes(controls.modelExperimentsBody).some(node => node.className === 'text-danger' && node.textContent === '-0.1000'));
});

test('saved report reopens without training and errors remain retryable', async () => {
    const {context, controls} = load({getControlledExperimentPlan: async () => plan,
        getModelReviewHistory: async () => [{type: 'controlled_experiment', evidence: report}],
        runControlledExperiments: async () => {throw new Error('busy');}});
    await vm.runInContext('openModelExperiments({model_id:"saved"})', context);
    assert.match(text(controls.modelExperimentsBody), /Results on the same unseen candles/);
    const button = nodes(controls.modelExperimentsBody).find(node => node.tag === 'button');
    await button.onclick();
    assert.equal(button.disabled, false);
    assert.match(text(controls.modelExperimentsBody), /Experiment failed: busy.*retry/);
});

test('stale plan responses cannot replace the selected model', async () => {
    const queue = [];
    const {context, controls} = load({getControlledExperimentPlan: id => new Promise(resolve => queue.push({id, resolve})), getModelReviewHistory: async () => []});
    const first = vm.runInContext('openModelExperiments({model_id:"first"})', context);
    const second = vm.runInContext('openModelExperiments({model_id:"second"})', context);
    queue[1].resolve({...plan, notes: ['second recipe']}); await second;
    queue[0].resolve({...plan, notes: ['first recipe']}); await first;
    assert.match(text(controls.modelExperimentsBody), /second recipe/);
    assert.doesNotMatch(text(controls.modelExperimentsBody), /first recipe/);
});

test('double clicks start only one job and failed preview has a retry instruction', async () => {
    let finish, count = 0;
    const {context, controls} = load({getControlledExperimentPlan: async () => plan, getModelReviewHistory: async () => [],
        runControlledExperiments: () => {count++; return new Promise(resolve => {finish = resolve;});}});
    await vm.runInContext('openModelExperiments({model_id:"selected"})', context);
    const button = nodes(controls.modelExperimentsBody).find(node => node.tag === 'button');
    const first = button.onclick();
    await button.onclick();
    assert.equal(count, 1);
    finish(report); await first;
    const failure = load({getControlledExperimentPlan: async () => {throw new Error('offline');}, getModelReviewHistory: async () => []});
    await vm.runInContext('openModelExperiments({model_id:"missing"})', failure.context);
    assert.match(text(failure.controls.modelExperimentsBody), /click Experiments to retry/);
});
