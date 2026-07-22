
let chart = null;
let series = null;


export function renderEquityCurve(
    equity,
    trades,
) {

    const container =
        document.getElementById("backtestEquityChart");

    if (!chart) {

        chart = LightweightCharts.createChart(
            container,
            {
                width: container.clientWidth,
                height: 300,

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
            }
        );

        series = chart.addSeries(
            LightweightCharts.LineSeries,
            {
                color: "#2962FF",
                lineWidth: 2,
            }
        );
    }

    const data = equity.map(x => ({
        time: Math.floor(
            new Date(x.time).getTime() / 1000
        ),
        value: x.equity,
    }));

    series.setData(data);


    chart.timeScale().fitContent();
}