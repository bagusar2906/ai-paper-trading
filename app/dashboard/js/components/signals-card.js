export function updateSignal(signal) {

    const table =
        document.getElementById("signalTable");

    if (!signal) {

        table.innerHTML =
            "<tr><td colspan='2'>No Signal</td></tr>";

        return;
    }

    const hasTradeLevels = signal.stop_loss != null
        && signal.take_profit != null;

    const stopLoss = hasTradeLevels
        ? signal.stop_loss.toFixed(2)
        : "Not applicable — HOLD";

    const takeProfit = hasTradeLevels
        ? signal.take_profit.toFixed(2)
        : "Not applicable — HOLD";

    const riskReward = hasTradeLevels
        ? `1 : ${signal.risk_reward}`
        : "-";

    table.innerHTML = `
        <tr><td>Action</td><td>${signal.action}</td></tr>
        <tr><td>Price</td><td>${signal.price.toFixed(2)}</td></tr>
        <tr><td>Confidence</td><td>${(signal.confidence * 100).toFixed(1)}%</td></tr>
        <tr><td>SL</td><td>${stopLoss}</td></tr>
        <tr><td>TP</td><td>${takeProfit}</td></tr>
        <tr><td>R:R</td><td>${riskReward}</td></tr>
    `;
}
