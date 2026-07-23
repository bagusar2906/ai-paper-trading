import { renderPriceChart }
    from "../charts/backtest-price-chart.js";

import { renderEquityCurve }
    from "../charts/equity-chart.js";

export function renderBacktest(report) {

    renderPriceChart(report);

    renderEquityCurve(report.equity);

    renderStatistics(report.statistics);

    renderTrades(report.trades);

    renderSummary(report.statistics);

}

function renderStatistics(stats) {

    document.getElementById("btTotalTrades").textContent =
        stats.total_trades;

    document.getElementById("btWinRate").textContent =
        stats.win_rate.toFixed(1) + "%";

    document.getElementById("btNetProfit").textContent =
        stats.net_profit.toFixed(2);

}

function renderTrades(trades) {

    const tbody =
        document.getElementById("btTrades");

    tbody.innerHTML = "";

    for (const trade of trades) {

        tbody.insertAdjacentHTML(
            "beforeend",
            `
            <tr>
                <td>${trade.symbol}</td>
                <td>${trade.side}</td>
                <td>${trade.entry_price.toFixed(2)}</td>
                <td>${trade.exit_price.toFixed(2)}</td>
                <td>${trade.pnl.toFixed(2)}</td>
            </tr>
            `
        );
    }

}

function renderEquity(equity) {

    console.log(
        "Equity points:",
        equity.length
    );

    // We'll draw the chart next.
}