let chart;
let candleSeries;
let emaSeries;

export function renderPriceChart(report) {

    console.log("=== renderPriceChart ===");
    console.log(report);

    const container =
        document.getElementById("backtestPriceChart");

    console.log("container:", container);

    console.log(
        "size:",
        container.clientWidth,
        container.clientHeight
    );

    console.log(
        "candles:",
        report.candles?.length
    );

    console.log(
        "ema:",
        report.ema?.length
    );

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

    console.log("Setting candle data...");

    candleSeries.setData(
        report.candles.map(c => ({
            time: Math.floor(new Date(c.time).getTime() / 1000),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }))
    );

    console.log("Setting EMA...");

    emaSeries.setData(
        report.ema.map(e => ({
            time: Math.floor(new Date(e.time).getTime() / 1000),
            value: e.value,
        }))
    );

    chart.timeScale().fitContent();

    console.log("Done.");
}