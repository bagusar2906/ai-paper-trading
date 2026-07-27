import { initializeBacktest }
    from "./backtest.js";

import {
    getStrategyProfiles,
    getStrategyProfile,
} from "../api.js";

initializeBacktest();
loadProfiles();

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

async function loadProfiles() {

    const response = await fetch("/strategy-profiles");

    const profiles = await response.json();

    console.log("Profiles:", profiles);

    const select = document.getElementById("btProfile");

    console.log("Select:", select);

    select.innerHTML = "";

    for (const profile of profiles) {

        console.log("Adding:", profile.name);

        select.insertAdjacentHTML(
            "beforeend",
            `<option value="${profile.id}">
                ${profile.name}
            </option>`
        );
    }
}

async function loadProfile(profileId) {

    const profile =
        await getStrategyProfile(profileId);

    const p = profile.parameters;

    document.getElementById("emaFast").value = p.ema_fast;
    document.getElementById("emaSlow").value = p.ema_slow;
    document.getElementById("rsiPeriod").value = p.rsi_period;
    document.getElementById("rsiBuy").value = p.rsi_buy;
    document.getElementById("rsiSell").value = p.rsi_sell;
    document.getElementById("stopLoss").value = p.stop_loss;
    document.getElementById("takeProfit").value = p.take_profit;
    document.getElementById("riskPercent").value = p.risk_percent;
}