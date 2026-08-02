export function renderSummary(stats) {

    const profitClass =
        stats.net_profit >= 0
            ? "summary-positive"
            : "summary-negative";

    document.getElementById(
        "backtestSummary"
    ).innerHTML = `

<div class="summary-grid">

<div class="summary-card">

<div class="summary-title">

Net Profit

</div>

<div class="summary-value ${profitClass}">

${stats.net_profit.toFixed(2)}

</div>

</div>

<div class="summary-card">

<div class="summary-title">

Win Rate

</div>

<div class="summary-value summary-neutral">

${stats.win_rate.toFixed(1)}%

</div>

</div>

<div class="summary-card">

<div class="summary-title">

Trades

</div>

<div class="summary-value">

${stats.total_trades}

</div>

</div>

<div class="summary-card">

<div class="summary-title">

Winning

</div>

<div class="summary-value summary-positive">

${stats.winning_trades}

</div>

</div>

<div class="summary-card">

<div class="summary-title">

Losing

</div>

<div class="summary-value summary-negative">

${stats.losing_trades}

</div>

</div>

</div>

`;
}