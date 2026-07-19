export function updateStatistics(statistics) {

    document.getElementById("totalTrades").textContent =
        statistics.total_trades;

    document.getElementById("winRate").textContent =
        statistics.win_rate.toFixed(1) + "%";

    document.getElementById("netProfit").textContent =
        statistics.net_profit.toFixed(2);

}