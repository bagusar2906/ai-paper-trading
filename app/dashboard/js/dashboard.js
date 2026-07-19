import { getDashboard, getChart } from "./api.js";

import { initializeChart, updateChart } from "./chart.js";

import { updateAccount } from "./components/account-card.js";
import { updateStatistics } from "./components/statistics-card.js";
import { updatePositions } from "./components/positions-table.js";
import { updateTrades } from "./components/trades-table.js";
import { updateSignals } from "./components/signals-table.js";
import { updateCurrentSignal } from "./components/current-signal.js";
import { updateSignal } from "./components/signals-card.js";

initializeChart();

async function refresh() {

    try {

        const dashboard = await getDashboard();

        updateAccount(dashboard.account);

        updateStatistics(dashboard.statistics);

        updateCurrentSignal(dashboard.current_signal);
        updateSignal(dashboard.current_signal);

        updatePositions(dashboard.positions);

        updateTrades(dashboard.trades);

        updateSignals(dashboard.signals);

        const chart = await getChart();

        updateChart(chart);

    }
    catch (error) {

        console.error(error);

    }

}

refresh();

setInterval(refresh, 5000);