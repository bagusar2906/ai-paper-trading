export function createTradeMarkers(trades) {

    return trades.map(t => ({

        time: Math.floor(
            new Date(t.opened_at).getTime() / 1000
        ),

        position:
            t.side === "BUY"
                ? "belowBar"
                : "aboveBar",

        color:
            t.side === "BUY"
                ? "#00aa00"
                : "#ff0000",

        shape:
            t.side === "BUY"
                ? "arrowUp"
                : "arrowDown",

        text:
            `${t.side}
P/L ${t.pnl.toFixed(2)}`

    }));

}