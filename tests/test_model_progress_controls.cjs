const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

class Element {
    constructor(tag = 'div') { this.tag = tag; this.children = []; this.textContent = ''; this.style = {}; this.attributes = {}; }
    append(...items) { this.children.push(...items); }
    replaceChildren() { this.children = []; this.textContent = ''; }
    setAttribute(key, value) { this.attributes[key] = value; }
    set innerHTML(value) { this.html = value; this.lastElementChild = new Element('td'); }
}
function load(extra = {}, file = 'model-progress.js') {
    const controls = Object.fromEntries(['modelProgressTitle', 'modelProgressBody', 'modelProgressModal'].map(id => [id, new Element()]));
    const context = vm.createContext({document: {getElementById: id => controls[id], createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag)},
        bootstrap: {Modal: {getOrCreateInstance: () => ({show() {}})}}, ...extra});
    const source = fs.readFileSync(`app/dashboard/js/components/${file}`, 'utf8').replace(/^import[\s\S]*?;/gm, '').replace(/export /g, '');
    vm.runInContext(source, context);
    return {context, controls};
}
function nodes(node) { return [node, ...node.children.flatMap(nodes)]; }
function text(node) { return nodes(node).map(item => item.textContent).join('\n'); }
function point(id, up, down, selected = false) {
    return {model_id: id, training_run_id: id, created_at: '2026-01-01T00:00:00Z', selected,
        metrics: {up: {roc_auc: up, brier_score: .2, precision: 0}, down: {roc_auc: down, brier_score: .1}}};
}
const report = {model_id: 'b', runs: [point('a', .5, null), point('b', .7, .8, true)],
    folds: [{label: 'Period 1', validation_start: '2026-01-01T00:00:00Z', metrics: {up: {roc_auc: .6}, down: {roc_auc: .7}}}],
    notes: ['Completed training results'], matching_history_available: true};

test('every model row opens progress for that exact model', () => {
    const chosen = [];
    const {context} = load({openModelProgress: model => chosen.push(model.model_id)}, 'model-operations.js');
    for (const status of ['candidate', 'champion', 'retired']) {
        context.model = {model_id: status, status, metrics: {}};
        const row = vm.runInContext('row(model, {})', context);
        row.lastElementChild.children.find(node => node.textContent === 'Progress').onclick();
    }
    assert.deepEqual(chosen, ['candidate', 'champion', 'retired']);
});

test('chart highlights selected model, keeps missing scores missing, and switches metric and view', () => {
    const {context, controls} = load(); context.report = report;
    vm.runInContext('renderModelProgress(document.getElementById("modelProgressBody"), report)', context);
    const body = controls.modelProgressBody;
    assert.equal(nodes(body).filter(node => node.tag === 'circle').length, 3);
    assert.ok(nodes(body).some(node => node.tag === 'circle' && node.attributes.r === '6'));
    assert.match(text(body), /Run 2 \(selected\)/);
    assert.ok(nodes(body).some(node => node.tag === 'td' && node.textContent === '—'));
    const metric = nodes(body).find(node => node.id === 'modelProgressMetric');
    metric.value = 'brier_score'; metric.onchange();
    assert.match(text(body), /Brier score: Lower is better/);
    const view = nodes(body).find(node => node.id === 'modelProgressView');
    view.value = 'folds'; view.onchange();
    assert.match(text(body), /No valid scores/);
    metric.value = 'roc_auc'; metric.onchange();
    assert.equal(nodes(body).filter(node => node.tag === 'circle').length, 2);
    assert.match(text(body), /Period 1/);
});

test('one run, old metadata, and no recorded metrics explain their limitations', () => {
    const {context, controls} = load();
    context.report = {...report, runs: [point('b', null, null, true)], matching_history_available: false};
    vm.runInContext('renderModelProgress(document.getElementById("modelProgressBody"), report)', context);
    assert.match(text(controls.modelProgressBody), /Only one matching run/);
    assert.match(text(controls.modelProgressBody), /Older metadata/);
    assert.match(text(controls.modelProgressBody), /No valid scores/);
    assert.equal(nodes(controls.modelProgressBody).filter(node => node.tag === 'svg').length, 0);
});

test('late responses cannot overwrite a newly selected model', async () => {
    const requests = [];
    const {context, controls} = load({getModelTrainingProgress: id => new Promise(resolve => requests.push({id, resolve}))});
    const first = vm.runInContext('openModelProgress({model_id:"first"})', context);
    const second = vm.runInContext('openModelProgress({model_id:"second"})', context);
    requests[1].resolve({...report, runs: [point('second', .8, .7, true)]}); await second;
    requests[0].resolve({...report, runs: [point('first', .5, null, true)]}); await first;
    assert.match(controls.modelProgressTitle.textContent, /second/);
    assert.match(text(controls.modelProgressBody), /second/);
    assert.doesNotMatch(text(controls.modelProgressBody), /first/);
});

test('failed request gives a retry path and both pages contain the dialog', async () => {
    const {context, controls} = load({getModelTrainingProgress: async () => {throw new Error('offline');}});
    await vm.runInContext('openModelProgress({model_id:"missing"})', context);
    assert.match(text(controls.modelProgressBody), /click Progress to retry/);
    for (const file of ['index.html', 'ai-model-lab.html']) {
        const html = fs.readFileSync(`app/dashboard/${file}`, 'utf8');
        for (const id of ['modelProgressModal', 'modelProgressTitle', 'modelProgressBody']) assert.equal(html.split(`id="${id}"`).length - 1, 1);
    }
});
