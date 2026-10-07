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
    const diagnostic = comparison.decision_diagnostic;
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
        ${comparison.history_saved === false ? '<div class="alert alert-warning">Comparison history could not be saved. These results are available for this run only.</div>' : comparison.history_saved === true ? '<p class="small text-success">Comparison saved to candidate review history.</p>' : ''}
        ${renderPredictionQuality(comparison.prediction_quality)}
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
        ${diagnostic ? `<hr><div><strong>Model-decision diagnostic</strong><div class="row small mt-1"><div class="col-md-4">Candles evaluated: <strong>${diagnostic.candles_evaluated}</strong></div><div class="col-md-4">Average probability difference: <strong>${Number(diagnostic.average_probability_difference).toFixed(4)}</strong></div><div class="col-md-4">Maximum probability difference: <strong>${Number(diagnostic.maximum_probability_difference).toFixed(4)}</strong></div></div><div class="row small mt-1"><div class="col-md-6">Different final decisions: <strong>${diagnostic.decision_disagreements}</strong></div><div class="col-md-6">Probability differences blocked by rules: <strong>${diagnostic.rule_blocked_disagreements}</strong></div></div><p class="small text-muted mb-0 mt-2">${diagnostic.summary}</p></div>` : ""}
        ${renderFilterDiagnostics(comparison.filter_diagnostics)}
    `;

}

function escapeComparisonText(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[character]);
}

function renderPredictionQuality(quality) {
    if (!quality) return '';
    if (quality.status !== 'completed') {
        return '<div class="alert alert-warning">Insufficient prediction evidence: no paired valid predictions with known future outcomes. Trading results alone cannot establish prediction quality.</div>';
    }
    const format = value => value == null ? 'Unavailable' : Number(value).toFixed(4);
    const rows = [
        ['Brier score (lower is better)', 'brier_score'],
        ['Log loss (lower is better)', 'log_loss'],
        ['ROC AUC (higher is better)', 'roc_auc'],
        ['Average probability', 'mean_probability'],
        ['Minimum probability', 'minimum_probability'],
        ['Maximum probability', 'maximum_probability'],
    ].map(([label, key]) => `<tr><th>${label}</th><td>${format(quality.candidate?.[key])}</td><td>${format(quality.champion?.[key])}</td><td>${format(quality.baseline?.[key])}</td></tr>`).join('');
    const bins = ['0–20%', '20–40%', '40–60%', '60–80%', '80–100%'];
    const distribution = bins.map((label, index) => `<tr><th>${label}</th><td>${quality.candidate.probability_bins[index]}</td><td>${quality.champion.probability_bins[index]}</td></tr>`).join('');
    return `<div class="mb-3"><h6>Prediction quality on the same candles</h6>
        <p class="small">Scored ${quality.samples} paired predictions; excluded ${quality.excluded_decisions} decisions with missing predictions or unknown future outcomes. Observed positive rate: ${(quality.positive_rate * 100).toFixed(1)}%.<br>Scored window: ${escapeComparisonText(quality.start_time)} to ${escapeComparisonText(quality.end_time)}.</p>
        <div class="table-responsive"><table class="table table-sm"><thead><tr><th>Metric</th><th>Candidate</th><th>Champion</th><th>Training-rate baseline</th></tr></thead><tbody>${rows}</tbody></table></div>
        <p class="small text-muted">${escapeComparisonText(quality.baseline_note)} ROC AUC is unavailable when the scored outcomes contain only one class. Better predictions may still produce identical trades.</p>
        <details><summary>Probability distribution</summary><table class="table table-sm"><thead><tr><th>Probability range</th><th>Candidate candles</th><th>Champion candles</th></tr></thead><tbody>${distribution}</tbody></table></details></div>`;
}

function renderFilterDiagnostics(diagnostics) {
    if (!diagnostics) return '';
    const labels = {adx: 'ADX', long_rsi: 'Long RSI', short_rsi: 'Short RSI', trend_up: 'Uptrend', trend_down: 'Downtrend', probability_threshold: 'Probability thresholds'};
    const list = (counts, names = {}) => Object.entries(counts).map(([key, count]) => `<li>${escapeComparisonText(names[key] || key)}: <strong>${count}</strong></li>`).join('') || '<li>None</li>';
    return `<hr><h6>Where signals were filtered</h6><div class="row">${['candidate', 'champion'].map(key => {
        const item = diagnostics[key];
        const mode = item.entry_modes?.model_probability ? 'Model probability entries; technical entry filters off' : 'Model probability with technical entry filters';
        return `<div class="col-md-6"><strong>${key === 'candidate' ? 'Candidate' : 'Champion'}</strong><p class="small mb-1">${mode}<br>BUY: ${item.actions.BUY} · SELL: ${item.actions.SELL} · HOLD: ${item.actions.HOLD}<br>Valid predictions: ${item.valid_predictions} · Unavailable: ${item.unavailable_predictions}</p><div class="small">Blocked by filters<ul>${list(item.blocked_by_filter, labels)}</ul>Execution outcomes for BUY/SELL signals<ul>${list(item.execution_outcomes)}</ul></div></div>`;
    }).join('')}</div><p class="small text-muted">Filter counts can overlap: one candle may fail several rules. Execution outcomes distinguish submitted orders from signals rejected by position or risk rules.</p>`;
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
