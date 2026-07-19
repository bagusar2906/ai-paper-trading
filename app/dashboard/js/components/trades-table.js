export function updateTrades(trades) {

    const tbody =
        document.querySelector("#trades tbody");

    if (!tbody)
        return;

    tbody.innerHTML = "";

    trades.forEach(trade => {

        tbody.innerHTML += `
        <tr>
            <td>${trade.symbol}</td>
            <td>${trade.side}</td>
            <td>${trade.entry_price.toFixed(2)}</td>
            <td>${trade.exit_price.toFixed(2)}</td>
            <td>${trade.pnl.toFixed(2)}</td>
        </tr>
        `;
    });

}