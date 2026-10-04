import {
    startBacktest,
    getBacktestProgress,
    cancelBacktest,
} from "../api.js";

import { renderBacktest } from "./backtest-renderer.js";

let activeJobId = null;

export function initializeBacktest() {

    document
        .getElementById("btnRunBacktest")
        .addEventListener(
            "click",
            handleBacktestButton
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

        candidate_model_id:
            document.getElementById("btCandidateModel").value || null,

    };

    showLoading("Starting backtest...");

    try {

        const job =
            await startBacktest(request);

        activeJobId = job.jobId;
        setBacktestButtonRunning();
        pollBacktest(job.jobId);

    }
    catch (error) {

        hideLoading();
        setBacktestButtonIdle();
        alert(`Could not start backtest: ${error.message}`);

    }

}

async function handleBacktestButton() {

    if (activeJobId) {

        const button = document.getElementById("btnRunBacktest");
        button.disabled = true;
        button.textContent = "Stopping…";

        try {
            await cancelBacktest(activeJobId);
        }
        catch (error) {
            button.disabled = false;
            button.textContent = "■ Stop Backtest";
            alert(`Could not stop backtest: ${error.message}`);
        }

        return;

    }

    executeBacktest();

}

function setBacktestButtonRunning() {

    const button = document.getElementById("btnRunBacktest");
    button.className = "btn btn-danger w-100";
    button.textContent = "■ Stop Backtest";
    button.disabled = false;

}

function setBacktestButtonIdle() {

    const button = document.getElementById("btnRunBacktest");
    button.className = "btn btn-primary w-100";
    button.textContent = "▶ Run Backtest";
    button.disabled = false;

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

            activeJobId = null;
            setBacktestButtonIdle();

            if (job.failed) {
                hideLoading();
                alert(job.status);
                return;
            }

            if (job.cancelled) {
                updateProgress(job.progress, job.status);
            }
            else {
                hideLoading();
            }

            renderBacktest(
                job.result
            );

        }

    }, 500);

}
