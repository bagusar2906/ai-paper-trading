import { runBacktest } from "../api.js";

export function initializeBacktest() {

    document
        .getElementById("btnRunBacktest")
        .addEventListener(
            "click",
            executeBacktest
        );

}

async function executeBacktest() {

    const request = {

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

    const report =
        await runBacktest(request);

    console.log(report);

}