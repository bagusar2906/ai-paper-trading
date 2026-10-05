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
    const readyForReview = gate?.eligible_for_human_review;
    const gateMessage = gate
        ? (readyForReview
            ? "Ready for human promotion review. Promotion is still manual and paper-only."
            : "Investigate or retrain before another comparison. The candidate does not yet meet the evidence gate.")
        : "Acceptance gate unavailable for this comparison.";
    const gateClass = readyForReview ? "alert-success" : "alert-warning";
    const checkLabels = {
        minimum_trades: "Minimum trade evidence",
        same_or_more_trades: "Same or more trades than champion",
        net_profit_not_worse: "Net profit is not worse",
        drawdown_not_worse: "Maximum drawdown is not worse",
        profit_factor_not_worse: "Profit factor is not worse",
    };
    const checks = Object.entries(gate?.checks || {}).map(([key, passed]) => `
        <li class="${passed ? "text-success" : "text-danger"}">
            <strong>${passed ? "Pass" : "Needs attention"}</strong> — ${checkLabels[key] || key.replaceAll("_", " ")}
        </li>
    `).join("");

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
        <div class="alert ${gateClass} mb-2"><strong>${gate?.recommendation?.replaceAll("_", " ") || "NO RECOMMENDATION"}</strong><br>${gateMessage}</div>
        ${checks ? `<div class="mb-2"><strong>Acceptance checks</strong><ul class="mb-0 mt-1">${checks}</ul></div>` : ""}
        ${gate?.reasons?.length ? `<div class="small text-muted">${gate.reasons.join(" ")}</div>` : ""}
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
