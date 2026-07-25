export function updateBacktestMarkers(series, trades) {

    console.log("Trades:", trades);

    const markers = [];

    for (const trade of trades) {

        //
        // Entry
        //
        console.log(
            trade.opened_at,
            trade.closed_at
        );
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
        // Exit
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

                text: trade.pnl.toFixed(0),

            });

        }

    }

    LightweightCharts.createSeriesMarkers(
        series,
        markers
    );

}