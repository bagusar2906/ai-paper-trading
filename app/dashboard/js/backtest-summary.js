export function renderSummary(stats) {

    const container =
        document.getElementById(
            "backtestSummary"
        );

    container.innerHTML = "";

    const cards = [

        {
            title: "Net Profit",
            value: stats.net_profit.toFixed(2)
        },

        {
            title: "Win Rate",
            value: stats.win_rate.toFixed(1) + "%"
        },

        {
            title: "Trades",
            value: stats.total_trades
        },

        {
            title: "Winning",
            value: stats.winning_trades
        },

        {
            title: "Losing",
            value: stats.losing_trades
        }

    ];

    for (const card of cards) {

        container.innerHTML += `

            <div class="summary-card">

                <div class="summary-title">

                    ${card.title}

                </div>

                <div class="summary-value">

                    ${card.value}

                </div>

            </div>

        `;
    }

}