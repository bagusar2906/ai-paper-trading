import { getDashboard, getChart } from "../api.js";
import { initializeModelOperations, refreshModelOperations } from "../components/model-operations.js";

import {
    initializeChart,
    updateChart
} from "../charts/chart.js";

import {
    initializeOrderTicket
} from "../components/order-ticket.js";

import {
    initializeEditPosition
} from "../components/edit-position.js";

import {
    initializeTradingMode
} from "../components/trading-mode.js";

import { updateAccount } from "../components/account-card.js";
import { updateStatistics } from "../components/statistics-card.js";
import { updatePositions } from "../components/positions-table.js";
import { updateTrades } from "../components/trades-table.js";
import { updateSignals } from "../components/signals-table.js";
import { updateCurrentSignal } from "../components/current-signal.js";
import { updateSignal } from "../components/signals-card.js";
import { updateActiveStrategy } from "../components/active-strategy.js";
import { initializeFundAdjustment } from "../components/fund-adjustment.js";
import { initializeMarketDataSettings } from "../components/market-data-settings.js";

const REFRESH_INTERVAL = 5000;
let modelOperationsVisible = false;

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        await initialize();

    }
);

async function initialize() {

    initializeChart();
    initializeOrderTicket();
    initializeEditPosition();
    initializeTradingMode();
    initializeFundAdjustment();
    initializeModelOperations();
    initializeTradesCollapse();
    initializeSignalHistoryCollapse();
    await initializeMarketDataSettings();

    window.addEventListener(
        "dashboard-refresh",
        refresh
    );

    await refresh();

    setInterval(
        refresh,
        REFRESH_INTERVAL
    );
    setInterval(() => {
        if (modelOperationsVisible) refreshModelOperations();
    }, 30000);

}

function initializeTradesCollapse() {

    const collapse = document.getElementById("recentTradesCollapse");
    const button = document.getElementById("btnToggleRecentTrades");

    collapse.addEventListener("shown.bs.collapse", () => {
        button.textContent = "Hide Trades";
        button.setAttribute("aria-expanded", "true");
    });

    collapse.addEventListener("hidden.bs.collapse", () => {
        button.textContent = "Show Trades";
        button.setAttribute("aria-expanded", "false");
    });
}

function initializeSignalHistoryCollapse() {

    const collapse = document.getElementById("signalHistoryCollapse");
    const button = document.getElementById("btnToggleSignalHistory");

    collapse.addEventListener("shown.bs.collapse", () => {
        button.textContent = "Hide Signals";
        button.setAttribute("aria-expanded", "true");
    });

    collapse.addEventListener("hidden.bs.collapse", () => {
        button.textContent = "Show Signals";
        button.setAttribute("aria-expanded", "false");
    });
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

    updateActiveStrategy(dashboard.active_strategy);
    updateModelOperationsVisibility(dashboard.active_strategy);

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
        dashboard.positions,
        dashboard.trading_mode
    );

    updateTrades(
        dashboard.trades
    );

    updateSignals(
        dashboard.signals
    );

}

function updateModelOperationsVisibility(activeStrategy) {

    const card = document.getElementById("aiModelOperations");
    const applicable = activeStrategy?.strategy_type?.toUpperCase() === "AI_ASSISTED_XGB";

    card.classList.toggle("d-none", !applicable);

    if (applicable && !modelOperationsVisible) {
        modelOperationsVisible = true;
        refreshModelOperations();
    }
    else if (!applicable) {
        modelOperationsVisible = false;
    }
}
