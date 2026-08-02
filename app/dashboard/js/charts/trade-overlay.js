let markerPrimitive = null;

export class TradeOverlay {

    constructor(chart, candleSeries) {

        this.chart = chart;

        this.candleSeries = candleSeries;

        this.lineSeries = [];

    }

    render(trades) {

        const markers = [];

        //
        // Remove previous trade lines
        //
        for (const line of this.lineSeries) {

            this.chart.removeSeries(line);

        }

        this.lineSeries = [];

        for (const trade of trades) {

            //
            // ENTRY MARKER
            //
            markers.push({

                time: Math.floor(
                    new Date(trade.opened_at).getTime() / 1000
                ),

                position:
                    trade.side === "BUY"
                        ? "belowBar"
                        : "aboveBar",

                color:
                    trade.side === "BUY"
                        ? "#22c55e"
                        : "#ef4444",

                shape:
                    trade.side === "BUY"
                        ? "arrowUp"
                        : "arrowDown",

                text: trade.side,

            });

            //
            // EXIT MARKER
            //
            if (trade.closed_at) {

                markers.push({

                    time: Math.floor(
                        new Date(trade.closed_at).getTime() / 1000
                    ),

                    position:
                        trade.side === "BUY"
                            ? "aboveBar"
                            : "belowBar",

                    color:
                        trade.pnl >= 0
                            ? "#2563eb"
                            : "#f97316",

                    shape: "circle",

                    text: trade.pnl.toFixed(1),

                });

            }

            //
            // ENTRY -> EXIT LINE
            //
            // if (trade.closed_at) {

            //     const color =
            //         trade.pnl >= 0
            //             ? "#22c55e"
            //             : "#ef4444";

            //     const tradeLine =
            //         this.chart.addSeries(
            //             LightweightCharts.LineSeries,
            //             {
            //                 color,
            //                 lineWidth: 2,
            //                 lastValueVisible: false,
            //                 priceLineVisible: false,
            //                 crosshairMarkerVisible: false,
            //             }
            //         );

            //     tradeLine.setData([

            //         {
            //             time: Math.floor(
            //                 new Date(trade.opened_at).getTime() / 1000
            //             ),
            //             value: trade.entry_price,
            //         },

            //         {
            //             time: Math.floor(
            //                 new Date(trade.closed_at).getTime() / 1000
            //             ),
            //             value: trade.exit_price,
            //         }

            //     ]);

            //     this.lineSeries.push(tradeLine);

            // }

        }

        //
        // Draw markers
        //
        markerPrimitive =
            LightweightCharts.createSeriesMarkers(
                this.candleSeries,
                markers
            );

    }

}