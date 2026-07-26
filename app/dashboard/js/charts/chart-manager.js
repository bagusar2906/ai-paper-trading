export class ChartManager {

    constructor(containerId, height = 500) {

        this.container =
            document.getElementById(containerId);

        this.chart =
            LightweightCharts.createChart(
                this.container,
                {
                    width: this.container.clientWidth,
                    height: height,
                    layout: {
                        background: {
                            color: "#ffffff",
                        },
                        textColor: "#333",
                    },
                    grid: {
                        vertLines: {
                            color: "#f0f0f0",
                        },
                        horzLines: {
                            color: "#f0f0f0",
                        },
                    },
                    rightPriceScale: {
                        borderColor: "#ddd",
                    },
                    timeScale: {
                        borderColor: "#ddd",
                    },
                }
            );

        window.addEventListener(
            "resize",
            () => {

                this.chart.applyOptions({

                    width:
                        this.container.clientWidth,

                });

            }
        );

    }

}