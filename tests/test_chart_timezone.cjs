const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

function load(file, context) {
    const source = fs.readFileSync(`app/dashboard/js/charts/${file}`, 'utf8')
        .replace(/^import[^;]*;/gm, '').replace(/export /g, '');
    vm.runInContext(source, context);
}

test('WIB labels convert instants across midnight and year boundaries', () => {
    const context = vm.createContext({ Intl, Date });
    load('chart-time.js', context);
    const instant = Date.parse('2026-10-09T09:50:00-04:00') / 1000;
    assert.equal(context.formatChartTick(instant, 3), '20:50');
    assert.equal(context.formatChartTime(instant), '09 Oct 2026, 20:50 WIB');
    const midnight = Date.parse('2026-12-31T17:00:05Z') / 1000;
    assert.equal(context.formatChartTime(midnight), '01 Jan 2027, 00:00 WIB');
    for (const [type, expected] of [[0, '2027'], [1, 'Jan'], [2, '01 Jan'], [3, '00:00'], [4, '00:00:05']]) {
        assert.equal(context.formatChartTick(midnight, type), expected);
    }
    assert.equal(context.formatChartTick({year: 2026, month: 10, day: 9}, 2), '09 Oct');
    assert.equal(context.formatChartTick('2026-10-09', 2), '09 Oct');
});

test('live and backtest charts use WIB labels while retaining candle instants', () => {
    const options = [];
    const datasets = [];
    const context = vm.createContext({ Intl, Date,
        document: {getElementById: () => ({clientWidth: 900})},
        window: {addEventListener() {}},
        updateMarkers() {}, updatePositionLines() {},
        LightweightCharts: {CrosshairMode: {Normal: 0}, createChart: (_, config) => {
            options.push(config);
            return {addSeries: () => ({setData: data => datasets.push(data)}),
                timeScale: () => ({setVisibleLogicalRange() {}})};
        }},
    });
    load('chart-time.js', context);
    load('chart.js', context);
    load('chart-manager.js', context);
    vm.runInContext('initializeChart(); new ChartManager("backtestPriceChart");', context);
    for (const config of options) {
        assert.equal(config.timeScale.tickMarkFormatter, context.formatChartTick);
        assert.equal(config.localization.timeFormatter, context.formatChartTime);
    }
    context.data = {candles: [{time: '2026-10-09T09:50:00-04:00', open: 1, high: 2, low: 1, close: 2}],
        ema20: [], ema50: [], markers: [], positions: []};
    vm.runInContext('updateChart(data)', context);
    assert.equal(datasets[0][0].time, Date.parse(context.data.candles[0].time) / 1000);
});
