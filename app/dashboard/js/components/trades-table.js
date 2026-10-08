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
            <td class="text-nowrap">${formatTradeTime(trade.opened_at)}</td>
            <td>${trade.exit_price.toFixed(2)}</td>
            <td class="text-nowrap">${formatTradeTime(trade.closed_at)}</td>
            <td>${trade.pnl.toFixed(2)}</td>
        </tr>
        `;
    });

}

function formatTradeTime(value) {
    if (!value) return "-";
    const time = new Date(value);
    return Number.isNaN(time.getTime()) ? "-" : time.toLocaleString();
}
