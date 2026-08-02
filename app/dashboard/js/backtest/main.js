import { initializeBacktest }
    from "./backtest.js";

initializeBacktest();

document
    .getElementById("btnToggleTrades")
    .addEventListener("click", () => {

        const div =
            document.getElementById(
                "tradeHistoryContainer"
            );

        const visible =
            div.style.display !== "none";

        div.style.display =
            visible
                ? "none"
                : "block";

    });