const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function load(file, controls, extra = {}) {
    const context = vm.createContext({
        console: { log() {} }, location: { reload() {} },
        document: { getElementById: id => controls[id] || null }, ...extra,
    });
    const source = fs.readFileSync(path.join(__dirname, '../app/dashboard/js', file), 'utf8')
        .replace(/^import[\s\S]*?;/gm, '').replace(/export /g, '');
    vm.runInContext(source, context);
    return context;
}

const field = value => ({ value, checked: false, disabled: false, addEventListener() {}, textContent: '' });

test('raw model selection turns off technical filters and uses fixed stop controls', () => {
    const controls = { strategyType: field('AI_ASSISTED_XGB'), btnSaveStrategy: field(''),
        feature_set_id: field('raw-ohlcv-v1'), use_technical_filters: field(''),
        adx_threshold: field(25), stop_atr_multiple: field(1.5), model_stop_loss_percent: field(.5) };
    controls.use_technical_filters.checked = true;
    const context = load('strategy/strategy-editor.js', controls);
    vm.runInContext('updateModelEntryFields()', context);
    assert.equal(controls.use_technical_filters.checked, false);
    assert.equal(controls.use_technical_filters.disabled, true);
    assert.equal(controls.adx_threshold.disabled, true);
    assert.equal(controls.stop_atr_multiple.disabled, true);
    assert.equal(controls.model_stop_loss_percent.disabled, false);
    controls.feature_set_id.value = 'core-v1';
    controls.use_technical_filters.checked = true;
    vm.runInContext('updateModelEntryFields()', context);
    assert.equal(controls.use_technical_filters.disabled, false);
    assert.equal(controls.adx_threshold.disabled, false);
    assert.equal(controls.model_stop_loss_percent.disabled, true);
});

test('strategy editor saves the checkbox as false and feature set as a string', async () => {
    let saved;
    const controls = { strategyType: field('AI_ASSISTED_XGB'), btnSaveStrategy: field(''),
        feature_set_id: field('raw-ohlcv-v1'), use_technical_filters: field(''),
        model_stop_loss_percent: field('1.25'), strategyName: field('Raw model'), strategyDescription: field('') };
    const context = load('strategy/strategy-editor.js', controls, { createStrategy: async payload => { saved = payload; } });
    vm.runInContext(`modal = { hide() {} }; currentSchema = [{key:'feature_set_id',type:'select'},{key:'use_technical_filters',type:'boolean'},{key:'model_stop_loss_percent',type:'number'}]`, context);
    await vm.runInContext('saveStrategy()', context);
    assert.deepEqual(JSON.parse(saved.config), { feature_set_id: 'raw-ohlcv-v1', use_technical_filters: false, model_stop_loss_percent: 1.25 });
});

test('self-training sends raw inputs and market settings and shows saved status', async () => {
    let sent;
    const controls = { candidateFeatureSetId: field('raw-ohlcv-v1'), candidateSymbol: field('EURUSD'), candidateTimeframe: field('H1'),
        selfTrainingInterval: field('15'), selfTrainingStatus: field(''), enableSelfTraining: field(''), disableSelfTraining: field(''),
        candidateBars: field('1000'), candidateHorizon: field('12'), candidateThreshold: field('.003'), candidateNEstimators: field('100'),
        candidateMaxDepth: field('3'), candidateLearningRate: field('.05'), candidateProbabilityThreshold: field('.5') };
    const context = load('components/model-operations.js', controls, {
        configureSelfTraining: async payload => {
            sent = payload;
            return { configuration: { enabled: payload.enabled, interval_minutes: 15, training: payload.training || {} }, last_run: {} };
        },
    });
    await vm.runInContext('setSelfTraining(true)', context);
    assert.equal(sent.training.feature_set_id, 'raw-ohlcv-v1');
    assert.equal(sent.training.symbol, 'EURUSD');
    assert.equal(sent.training.timeframe, 'H1');
    assert.equal(sent.training.bars, 1000);
    assert.equal(sent.interval_minutes, 15);
    assert.match(controls.selfTrainingStatus.textContent, /Enabled: EURUSD H1, raw price and volume/);
    await vm.runInContext('setSelfTraining(false)', context);
    assert.equal(sent.enabled, false);
    assert.match(controls.selfTrainingStatus.textContent, /Self-training is off/);
});
