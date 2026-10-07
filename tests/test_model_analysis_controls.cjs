const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

class Element {
    constructor() { this.children = []; this.textContent = ''; }
    append(...items) { this.children.push(...items); }
    replaceChildren() { this.children = []; this.textContent = ''; }
    set innerHTML(value) { this.html = value; this.lastElementChild = new Element(); }
    get innerHTML() { return this.html; }
}
function load(extra = {}) {
    const controls = Object.fromEntries(['modelAnalysisBody', 'modelAnalysisTitle', 'modelAnalysisModal'].map(id => [id, new Element()]));
    const context = vm.createContext({ document: {getElementById: id => controls[id], createElement: () => new Element()},
        bootstrap: {Modal: {getOrCreateInstance: () => ({show() {}})}}, ...extra });
    const source = fs.readFileSync('app/dashboard/js/components/model-operations.js', 'utf8')
        .replace(/^import[\s\S]*?;/gm, '').replace(/export /g, '');
    vm.runInContext(source, context);
    return {context, controls};
}
const report = {
    source: 'ai', summary: '<script>unsafe()</script>', evidence: {target: 'UP after 12 candles',
        feature_set_id: 'raw-ohlcv-v1', validation_observations: 200, fold_count: 2, probability_threshold: .6,
        fold_ranges: {precision: {min: .5, max: .8, folds_with_score: 2}},
        calibration_bins: [{count: 100, mean_probability: .7, observed_rate: .5}]},
    metrics: [{key: 'precision', name: 'Precision', value: .75, explanation: 'Share of predicted UP events that met the target.'}],
    strengths: [], limitations: ['Small sample'], evidence_notes: ['Not a profit estimate'], next_steps: ['Paper test'], history_saved: true,
};
function allText(element) { return [element.textContent, ...element.children.map(allText)].join('\n'); }

test('analysis renderer shows scores, calibration and escaped AI prose', () => {
    const {context, controls} = load();
    context.report = report;
    vm.runInContext('renderModelAnalysis(document.getElementById("modelAnalysisBody"), report)', context);
    const body = controls.modelAnalysisBody;
    assert.match(allText(body), /Precision: 75.0%/);
    assert.match(allText(body), /Fold range: 0.500–0.800/);
    assert.match(allText(body), /Predicted 70.0% · Actual 50.0%/);
    assert.match(allText(body), /Not a profit estimate/);
    assert.ok(body.children.some(item => item.textContent === '<script>unsafe()</script>'));
    assert.ok(body.children.every(item => item.html === undefined));
});

test('every model status offers Analyze', () => {
    const {context} = load();
    for (const status of ['candidate', 'champion', 'retired']) {
        context.model = {model_id: 'm1', status, metrics: {}};
        const row = vm.runInContext('row(model, {})', context);
        assert.ok(row.lastElementChild.children.some(item => item.textContent === 'Analyze'));
    }
});

test('older request cannot overwrite the selected model analysis', async () => {
    const requests = [];
    const {context, controls} = load({analyzeModel: id => new Promise(resolve => requests.push({id, resolve}))});
    const first = vm.runInContext('openModelAnalysis({model_id:"first"})', context);
    const second = vm.runInContext('openModelAnalysis({model_id:"second"})', context);
    requests[1].resolve({...report, summary: 'Second model report'});
    await second;
    requests[0].resolve({...report, summary: 'First model report'});
    await first;
    assert.match(controls.modelAnalysisTitle.textContent, /second/);
    assert.match(allText(controls.modelAnalysisBody), /Second model report/);
    assert.doesNotMatch(allText(controls.modelAnalysisBody), /First model report/);
});

test('failed analysis shows a retry path and local reports identify fallback', async () => {
    const {context, controls} = load({analyzeModel: async () => {throw new Error('offline');}});
    await vm.runInContext('openModelAnalysis({model_id:"m1"})', context);
    assert.match(controls.modelAnalysisBody.textContent, /click Analyze to retry/);
    context.report = {...report, source: 'local_evidence', source_note: 'AI is not configured.', history_saved: false};
    vm.runInContext('renderModelAnalysis(document.getElementById("modelAnalysisBody"), report)', context);
    assert.match(allText(controls.modelAnalysisBody), /Local evidence analysis/);
    assert.match(allText(controls.modelAnalysisBody), /could not be saved/);
});

test('analysis modal exists in both model tables', () => {
    for (const file of ['index.html', 'ai-model-lab.html']) {
        const html = fs.readFileSync(`app/dashboard/${file}`, 'utf8');
        for (const id of ['modelAnalysisModal', 'modelAnalysisTitle', 'modelAnalysisBody']) {
            assert.equal(html.split(`id="${id}"`).length - 1, 1);
        }
    }
});
