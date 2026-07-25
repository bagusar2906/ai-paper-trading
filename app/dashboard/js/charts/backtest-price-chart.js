import {
    updateBacktestMarkers
}
from "./backtest-markers.js";

let chart;
let candleSeries;
let emaSeries;

export function renderPriceChart(report) {


    const container =
        document.getElementById("backtestPriceChart");


    if (!chart) {

        console.log("Creating chart...");

        chart = LightweightCharts.createChart(
            container,
            {
                width: container.clientWidth,
                height: 550,
            }
        );

        candleSeries = chart.addSeries(
            LightweightCharts.CandlestickSeries
        );

        emaSeries = chart.addSeries(
            LightweightCharts.LineSeries,
            {
                color: "#2962FF",
                lineWidth: 2,
            }
        );
    }


    candleSeries.setData(
        report.candles.map(c => ({
            time: Math.floor(new Date(c.time).getTime() / 1000),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }))
    );

    emaSeries.setData(
        report.ema.map(e => ({
            time: Math.floor(new Date(e.time).getTime() / 1000),
            value: e.value,
        }))
    );

    updateBacktestMarkers(
        candleSeries,
        report.trades
    );

    chart.timeScale().fitContent();

}