import { renderPriceChart }
    from "../charts/backtest-price-chart.js";

import { renderEquityCurve }
    from "../charts/equity-chart.js";

import { renderSummary }
    from "./backtest-summary.js";

export function renderBacktest(report) {

    renderPriceChart(report);

    renderEquityCurve(report.equity);

    renderTrades(report.trades);

    renderSummary(report.statistics);

    renderCandidateComparison(report.comparison);

}

function renderCandidateComparison(comparison) {

    const card = document.getElementById("candidateComparisonCard");
    const target = document.getElementById("candidateComparison");

    if (!comparison) {
        card.classList.add("d-none");
        target.replaceChildren();
        return;
    }

    card.classList.remove("d-none");

    if (comparison.status !== "completed") {
        target.textContent = "Comparison was stopped before the champion replay completed.";
        return;
    }

    const candidate = comparison.candidate;
    const champion = comparison.champion;
    const difference = candidate.net_profit - champion.net_profit;
    const differenceClass = difference >= 0 ? "text-success" : "text-danger";
    const gate = comparison.acceptance_gate;
    const gateMessage = gate
        ? (gate.eligible_for_human_review
            ? "Candidate meets the minimum evidence gate for human review. It is not promoted automatically."
            : "Candidate does not yet meet the minimum evidence gate; investigate or collect more evidence.")
        : "Acceptance gate unavailable for this comparison.";
    const gateClass = gate?.eligible_for_human_review ? "text-success" : "text-warning";

    target.innerHTML = `
        <p class="mb-3">Held-out window starts ${new Date(comparison.evaluation_start).toLocaleString()}. Both models used the same candles and paper-only execution path.</p>
        <div class="table-responsive"><table class="table table-sm mb-2">
            <thead><tr><th>Metric</th><th>Candidate</th><th>Champion</th></tr></thead>
            <tbody>
                <tr><th>Model</th><td>${comparison.candidate_model_id}</td><td>${comparison.champion_model_id}</td></tr>
                <tr><th>Net profit</th><td>${candidate.net_profit.toFixed(2)}</td><td>${champion.net_profit.toFixed(2)}</td></tr>
                <tr><th>Profit factor</th><td>${candidate.profit_factor.toFixed(2)}</td><td>${champion.profit_factor.toFixed(2)}</td></tr>
                <tr><th>Max drawdown</th><td>${candidate.max_drawdown.toFixed(2)}</td><td>${champion.max_drawdown.toFixed(2)}</td></tr>
                <tr><th>Win rate</th><td>${candidate.win_rate.toFixed(1)}%</td><td>${champion.win_rate.toFixed(1)}%</td></tr>
                <tr><th>Trades</th><td>${candidate.total_trades}</td><td>${champion.total_trades}</td></tr>
            </tbody>
        </table></div>
        <p class="mb-2 ${differenceClass}">Net-profit difference: ${difference >= 0 ? "+" : ""}${difference.toFixed(2)}. Review trade count, drawdown, and the training metrics before manual promotion.</p>
        <p class="mb-0 ${gateClass}">${gateMessage}</p>
    `;

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
