let priceLines = [];

export function updatePositionLines(candleSeries, positions) {

    // Remove existing lines
    priceLines.forEach(line => {
        candleSeries.removePriceLine(line);
    });

    priceLines = [];

    positions.forEach(position => {

        const entryColor =
            position.side === "BUY"
                ? "#22c55e"
                : "#ef4444";

        // Entry
        priceLines.push(
            candleSeries.createPriceLine({
                price: position.entry,
                color: entryColor,
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: `${position.side} ENTRY`,
            })
        );

        // Stop Loss
        priceLines.push(
            candleSeries.createPriceLine({
                price: position.stop_loss,
                color: "#ef4444",
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: "SL",
            })
        );

        // Take Profit
        priceLines.push(
            candleSeries.createPriceLine({
                price: position.take_profit,
                color: "#22c55e",
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: "TP",
            })
        );

    });

}