const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function render(comparison) {
    const target = { innerHTML: '', textContent: '', replaceChildren() {} };
    const card = { classList: { add() {}, remove() {} } };
    const context = vm.createContext({ document: { getElementById: id => id === 'candidateComparisonCard' ? card : target } });
    const source = fs.readFileSync(path.join(__dirname, '../app/dashboard/js/backtest/backtest-renderer.js'), 'utf8')
        .replace(/^import[\s\S]*?;/gm, '').replace('export function', 'function');
    vm.runInContext(source, context);
    context.comparison = comparison;
    vm.runInContext('renderCandidateComparison(comparison)', context);
    return target;
}

function fixture() {
    const stats = { net_profit: 0, profit_factor: 0, max_drawdown: 0, win_rate: 0, total_trades: 0 };
    const scores = { brier_score: .01, log_loss: .1, roc_auc: null, mean_probability: .1,
        minimum_probability: .05, maximum_probability: .2, probability_bins: [3, 1, 0, 0, 0] };
    const filters = { actions: { BUY: 0, SELL: 1, HOLD: 3 }, valid_predictions: 4,
        unavailable_predictions: 0, blocked_by_filter: { adx: 2 },
        execution_outcomes: { 'Position already exists for XAUUSD': 1 } };
    return { status: 'completed', candidate: stats, champion: stats,
        candidate_model_id: 'candidate', champion_model_id: 'champion',
        evaluation_start: '2026-01-01T00:00:00Z', history_saved: true,
        prediction_quality: { status: 'completed', samples: 4, excluded_decisions: 1,
            positive_rate: .25, candidate: scores, champion: scores, baseline: null,
            baseline_note: 'Training rate unavailable <script>alert(1)</script>',
            start_time: '2026-01-01T00:00:00Z', end_time: '2026-01-01T00:15:00Z' },
        filter_diagnostics: { candidate: filters, champion: filters } };
}

test('renders metrics, missing baseline, single-class AUC and filter counts safely', () => {
    const html = render(fixture()).innerHTML;
    assert.match(html, /Prediction quality on the same candles/);
    assert.match(html, /0\.0100/);
    assert.match(html, /Unavailable/);
    assert.match(html, /Position already exists for XAUUSD/);
    assert.match(html, /Comparison saved/);
    assert.match(html, /&lt;script&gt;/);
    assert.doesNotMatch(html, /<script>/);
    assert.doesNotMatch(html, /undefined|NaN/);
});

test('shows insufficient prediction evidence and history save failure', () => {
    const comparison = fixture();
    comparison.history_saved = false;
    comparison.prediction_quality = { status: 'insufficient_evidence' };
    const html = render(comparison).innerHTML;
    assert.match(html, /Insufficient prediction evidence/);
    assert.match(html, /history could not be saved/);
});

test('handles old reports and cancelled comparisons', () => {
    const comparison = fixture();
    delete comparison.prediction_quality;
    delete comparison.filter_diagnostics;
    assert.doesNotMatch(render(comparison).innerHTML, /undefined|NaN/);
    assert.match(render({ status: 'stopped' }).textContent, /stopped/);
    render(null);
});

test('comparison identifies model probability mode', () => {
    const comparison = fixture();
    comparison.filter_diagnostics.candidate.entry_modes = { model_probability: 4 };
    assert.match(render(comparison).innerHTML, /technical entry filters off/);
});
