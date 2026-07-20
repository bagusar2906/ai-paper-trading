import { getDashboard, getChart } from "./api.js";

import {
    initializeChart,
    updateChart
} from "./chart.js";

import {
    initializeOrderTicket
} from "./components/order-ticket.js";

import { updateAccount } from "./components/account-card.js";
import { updateStatistics } from "./components/statistics-card.js";
import { updatePositions } from "./components/positions-table.js";
import { updateTrades } from "./components/trades-table.js";
import { updateSignals } from "./components/signals-table.js";
import { updateCurrentSignal } from "./components/current-signal.js";
import { updateSignal } from "./components/signals-card.js";

const REFRESH_INTERVAL = 5000;

initialize();

async function initialize() {

    initializeChart();

    initializeOrderTicket();

    window.addEventListener(
        "dashboard-refresh",
        refresh
    );

    await refresh();

    setInterval(
        refresh,
        REFRESH_INTERVAL
    );

}

async function refresh() {

    try {

        const [dashboard, chart] = await Promise.all([
            getDashboard(),
            getChart()
        ]);

        renderDashboard(dashboard);

        updateChart(chart);

    }
    catch (error) {

        console.error(
            "Dashboard refresh failed",
            error
        );

    }

}

function renderDashboard(dashboard) {

    updateAccount(
        dashboard.account
    );

    updateStatistics(
        dashboard.statistics
    );

    updateCurrentSignal(
        dashboard.current_signal
    );

    updateSignal(
        dashboard.current_signal
    );

    updatePositions(
        dashboard.positions
    );

    updateTrades(
        dashboard.trades
    );

    updateSignals(
        dashboard.signals
    );

}