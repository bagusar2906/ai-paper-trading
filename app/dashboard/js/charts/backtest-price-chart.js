import { ChartManager }
    from "./chart-manager.js";

import { TradeOverlay }
    from "./trade-overlay.js";

let manager;

let candleSeries;

let emaSeries;

let tradeOverlay;

export function renderPriceChart(report) {

    if (!manager) {

        manager =
            new ChartManager(
                "backtestPriceChart",
                550
            );

        candleSeries =
            manager.chart.addSeries(
                LightweightCharts.CandlestickSeries
            );

        emaSeries =
            manager.chart.addSeries(
                LightweightCharts.LineSeries,
                {
                    color: "#2962FF",
                    lineWidth: 2,
                }
            );

        //
        // Create trade overlay
        //
        tradeOverlay =
            new TradeOverlay(
                manager.chart,
                candleSeries
            );

    }

    //
    // Candles
    //
    candleSeries.setData(

        report.candles.map(c => ({

            time: Math.floor(
                new Date(c.time).getTime() / 1000
            ),

            open: c.open,

            high: c.high,

            low: c.low,

            close: c.close,

        }))

    );

    //
    // EMA
    //
    emaSeries.setData(

        report.ema.map(e => ({

            time: Math.floor(
                new Date(e.time).getTime() / 1000
            ),

            value: e.value,

        }))

    );

    //
    // Draw trades
    //
    tradeOverlay.render(
        report.trades
    );

    manager.chart.timeScale().fitContent();

}