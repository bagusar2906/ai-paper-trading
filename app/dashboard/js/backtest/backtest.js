import {
    startBacktest,
    getBacktestProgress,
} from "../api.js";

import { renderBacktest } from "./backtest-renderer.js";

export function initializeBacktest() {

    document
        .getElementById("btnRunBacktest")
        .addEventListener(
            "click",
            executeBacktest
        );

}

function showLoading(status) {

    console.log("SHOW LOADING");

    document
        .getElementById("backtestLoading")
        .classList
        .remove("hidden");

    document
        .getElementById("backtestStatus")
        .textContent = status;

    document
        .getElementById("backtestProgress")
        .value = 0;
}

function hideLoading() {

    document
        .getElementById("backtestLoading")
        .classList
        .add("hidden");
}

function updateProgress(progress, status) {

    document.getElementById(
        "backtestProgress"
    ).value = progress;

    document.getElementById(
        "backtestPercent"
    ).innerText = progress + "%";

    document.getElementById(
        "backtestStatus"
    ).innerText = status;

}

async function executeBacktest() {

    const request = {

        strategy_id:

            parseInt(
                document.getElementById(
                    "btStrategy"
                ).value
            ),


        symbol:
            document.getElementById("btSymbol").value,

        timeframe:
            document.getElementById("btTimeframe").value,

        bars:
            parseInt(
                document.getElementById("btBars").value
            ),

        initial_balance:
            parseFloat(
                document.getElementById("btBalance").value
            ),

    };

    showLoading("Starting backtest...");

    const job =
        await startBacktest(request);

    pollBacktest(job.jobId);

}

async function pollBacktest(jobId) {

    const timer = setInterval(async () => {

        const job =
            await getBacktestProgress(jobId);

        updateProgress(
            job.progress,
            job.status
        );

        if (job.finished) {

            clearInterval(timer);

            hideLoading();

            renderBacktest(
                job.result
            );

        }

    }, 500);

}
