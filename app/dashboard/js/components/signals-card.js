export function updateSignal(signal) {

    const table =
        document.getElementById("signalTable");

    if (!signal) {

        table.innerHTML =
            "<tr><td colspan='2'>No Signal</td></tr>";

        return;
    }

    table.innerHTML = `
        <tr><td>Action</td><td>${signal.action}</td></tr>
        <tr><td>Price</td><td>${signal.price.toFixed(2)}</td></tr>
        <tr><td>Confidence</td><td>${signal.confidence.toFixed(1)}%</td></tr>
        <tr><td>SL</td><td>${signal.sl ? signal.stop_loss.toFixed(2) : ''}</td></tr>
        <tr><td>TP</td><td>${signal.tp ? signal.take_profit.toFixed(2) : ''}</td></tr>
        <tr><td>R:R</td><td>1 : ${signal.risk_reward}</td></tr>
    `;
}