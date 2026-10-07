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
        candidateDataSource: field('yahoo'),
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
    assert.equal(sent.training.data_source, 'yahoo');
    assert.equal(sent.training.symbol, 'EURUSD');
    assert.equal(sent.training.timeframe, 'H1');
    assert.equal(sent.training.bars, 1000);
    assert.equal(sent.interval_minutes, 15);
    assert.match(controls.selfTrainingStatus.textContent, /Enabled: EURUSD H1, raw price and volume/);
    await vm.runInContext('setSelfTraining(false)', context);
    assert.equal(sent.enabled, false);
    assert.match(controls.selfTrainingStatus.textContent, /Self-training is off/);
});

test('manual training preserves selected raw inputs and market settings', async () => {
    let sent;
    const controls = { candidateFeatureSetId: field('raw-ohlcv-v1'), candidateSymbol: field('EURUSD'), candidateTimeframe: field('H1'),
        candidateDataSource: field('mt5'),
        candidateBars: field('1000'), candidateHorizon: field('12'), candidateThreshold: field('.003'), candidateNEstimators: field('100'),
        candidateMaxDepth: field('3'), candidateLearningRate: field('.05'), candidateProbabilityThreshold: field('.6'),
        candidateTrainingStatus: field(''), trainCandidateModal: field(''), submitCandidateTraining: field('') };
    const context = load('components/model-operations.js', controls, {
        trainCandidate: async payload => {sent = payload; return {status: 'duplicate', message: 'unchanged'};},
    });
    await vm.runInContext('train(document.getElementById("submitCandidateTraining"))', context);
    assert.equal(sent.feature_set_id, 'raw-ohlcv-v1');
    assert.equal(sent.data_source, 'mt5');
    assert.equal(sent.symbol, 'EURUSD');
    assert.equal(sent.timeframe, 'H1');
    assert.equal(sent.probability_threshold, .6);
    assert.equal(controls.submitCandidateTraining.disabled, false);
});

test('self-training status explains data catch-up and the training window', () => {
    const controls = {selfTrainingStatus: field(''), disableSelfTraining: field('')};
    const context = load('components/model-operations.js', controls);
    context.report = {configuration: {enabled: true, interval_minutes: 60, training: {symbol: 'XAUUSD', timeframe: 'M5'}},
        running: false, last_run: {status: 'candidate_created', data_sync: {downloaded_bars: 2500,
            resumed_from: '2026-01-01T00:00:00Z', last_candle_at: '2026-01-07T00:00:00Z', training_window_bars: 1000}}};
    vm.runInContext('showSelfTrainingStatus(report)', context);
    assert.match(controls.selfTrainingStatus.textContent, /2500 new candles saved, resumed from/);
    assert.match(controls.selfTrainingStatus.textContent, /Training uses the latest 1000 candles/);
});

test('Model Lab loads and saves only its separate source preference', async () => {
    const controls = {candidateDataSource: field('trading'), modelLabDataSourceStatus: field('')};
    const listeners = {};
    controls.candidateDataSource.addEventListener = (type, listener) => {listeners[type] = listener;};
    const saved = [];
    const context = load('components/model-operations.js', controls, {
        getModelLabDataSource: async () => ({data_source: 'yahoo'}),
        setModelLabDataSource: async source => {saved.push(source); return {data_source: source};},
        updateSettings: () => assert.fail('Must not update trading settings'),
    });
    await vm.runInContext('initializeModelDataSource()', context);
    assert.equal(controls.candidateDataSource.value, 'yahoo');
    assert.equal(controls.candidateDataSource.disabled, false);
    controls.candidateDataSource.value = 'mt5';
    await listeners.change();
    assert.deepEqual(saved, ['mt5']);
    assert.match(controls.modelLabDataSourceStatus.textContent, /MetaTrader 5/);
    assert.match(controls.modelLabDataSourceStatus.textContent, /apply changes to background training/);
});

test('training waits for source loading and reports unsaved choices honestly', async () => {
    let resolve;
    const listeners = {};
    const controls = {candidateDataSource: field('trading'), modelLabDataSourceStatus: field(''),
        candidateTrainingStatus: field(''), selfTrainingStatus: field('')};
    controls.candidateDataSource.addEventListener = (type, listener) => {listeners[type] = listener;};
    const context = load('components/model-operations.js', controls, {
        getModelLabDataSource: () => new Promise(done => {resolve = done;}),
        setModelLabDataSource: async () => {throw new Error('offline');},
        trainCandidate: () => assert.fail('Must wait for source'), configureSelfTraining: () => assert.fail('Must wait for source'),
    });
    const pending = vm.runInContext('initializeModelDataSource()', context);
    await vm.runInContext('train({})', context);
    await vm.runInContext('setSelfTraining(true)', context);
    assert.match(controls.candidateTrainingStatus.textContent, /Wait for the data-source/);
    assert.match(controls.selfTrainingStatus.textContent, /Wait for the data-source/);
    resolve({data_source: 'oanda'});
    await pending;
    controls.candidateDataSource.value = 'mt5';
    await listeners.change();
    assert.match(controls.modelLabDataSourceStatus.textContent, /preference was not saved/);
    assert.equal(controls.candidateDataSource.disabled, false);
});

test('source selector offers all supported sources on both pages', () => {
    for (const file of ['index.html', 'ai-model-lab.html']) {
        const html = fs.readFileSync(path.join(__dirname, '../app/dashboard', file), 'utf8');
        assert.equal(html.split('id="candidateDataSource"').length - 1, 1);
        for (const value of ['trading', 'mt5', 'oanda', 'yahoo', 'twelve_data']) assert.ok(html.includes(`value="${value}"`));
    }
});

test('candidate replacement is selected by default and can retain every version', () => {
    const controls = {};
    const context = load('components/model-operations.js', controls);
    assert.equal(vm.runInContext('trainingParameters().replace_previous_candidate', context), true);
    controls.candidateReplacePrevious = field('');
    controls.candidateReplacePrevious.checked = false;
    assert.equal(vm.runInContext('trainingParameters().replace_previous_candidate', context), false);
    for (const name of ['index.html', 'ai-model-lab.html']) {
        const html = fs.readFileSync(path.join(__dirname, '../app/dashboard', name), 'utf8');
        assert.match(html, /id="candidateReplacePrevious"[^>]* checked/);
    }
});

test('self-training restores the replacement checkbox as a boolean', async () => {
    const controls = {candidateReplacePrevious: field(''), selfTrainingStatus: field(''), selfTrainingInterval: field('')};
    controls.candidateReplacePrevious.checked = true;
    const context = load('components/model-operations.js', controls, {
        getSelfTrainingStatus: async () => ({configuration: {enabled: true, interval_minutes: 60,
            training: {replace_previous_candidate: false}}, last_run: {replaced_model_ids: ['old-1']}}),
    });
    await vm.runInContext('refreshSelfTraining(true)', context);
    assert.equal(controls.candidateReplacePrevious.checked, false);
    assert.match(controls.selfTrainingStatus.textContent, /Keeps every trained candidate/);
    assert.match(controls.selfTrainingStatus.textContent, /Replaced 1 previous candidate/);
});
