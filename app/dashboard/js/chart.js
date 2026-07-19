let chart;

let candleSeries;
let ema20Series;
let ema50Series;

export function initializeChart() {

    const container = document.getElementById("chart");

    chart = LightweightCharts.createChart(container, {

        width: container.clientWidth,

        height: 500,

        layout: {
            background: {
                color: "#ffffff",
            },
            textColor: "#333",
        },

        grid: {
            vertLines: {
                color: "#eeeeee",
            },
            horzLines: {
                color: "#eeeeee",
            },
        },

        rightPriceScale: {
            borderVisible: false,
        },

        timeScale: {
            borderVisible: false,
            timeVisible: true,
        },

        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },

    });

    candleSeries = chart.addSeries(
        LightweightCharts.CandlestickSeries,
        {
            upColor: "#26a69a",
            downColor: "#ef5350",

            borderUpColor: "#26a69a",
            borderDownColor: "#ef5350",

            wickUpColor: "#26a69a",
            wickDownColor: "#ef5350",
        }
    );

    ema20Series = chart.addSeries(
        LightweightCharts.LineSeries,
        {
            color: "#2962FF",
            lineWidth: 2,
            priceLineVisible: false,
        }
    );

    ema50Series = chart.addSeries(
        LightweightCharts.LineSeries,
        {
            color: "#FF6D00",
            lineWidth: 2,
            priceLineVisible: false,
        }
    );

    window.addEventListener("resize", () => {

        chart.applyOptions({
            width: container.clientWidth,
        });

    });

}

export function updateChart(data) {

    if (!data)
        return;

    candleSeries.setData(

        data.candles.map(c => ({

            time: Math.floor(new Date(c.time).getTime() / 1000),

            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,

        }))

    );

    ema20Series.setData(

        data.ema20.map(e => ({

            time: Math.floor(new Date(e.time).getTime() / 1000),

            value: e.value,

        }))

    );

    ema50Series.setData(

        data.ema50.map(e => ({

            time: Math.floor(new Date(e.time).getTime() / 1000),

            value: e.value,

        }))

    );

    chart.timeScale().fitContent();

}