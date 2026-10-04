import { getStrategies }
    from "../strategy/strategy-api.js";

import { initializeBacktest }
    from "./backtest.js";

import { getModels }
    from "../api.js";

const strategiesById = new Map();
const requestedCandidateId = new URLSearchParams(window.location.search).get("candidate_model_id");

async function loadStrategies() {

    const strategies =
        await getStrategies();

    const select =
        document.getElementById(
            "btStrategy"
        );

    select.innerHTML = "";

    for (const strategy of strategies) {

        strategiesById.set(String(strategy.id), strategy);

        select.insertAdjacentHTML(

            "beforeend",

            `
            <option value="${strategy.id}">
                ${strategy.name}
            </option>
            `
        );

    }

    select.addEventListener("change", updateCandidateComparisonAvailability);
    updateCandidateComparisonAvailability();

}

async function loadCandidateModels() {

    const select = document.getElementById("btCandidateModel");
    const contextHint = document.getElementById("btCandidateModelContext");
    const candidates = new Map();

    try {
        const models = await getModels();

        for (const model of models.filter(model => model.status === "candidate")) {
            candidates.set(model.model_id, model);
            const option = document.createElement("option");
            option.value = model.model_id;
            option.textContent = model.market_context
                ? `${model.model_id} — ${model.market_context.symbol} / ${model.market_context.timeframe}`
                : `${model.model_id} — retrain required`;
            select.append(option);
        }

        select.addEventListener("change", () => {
            const model = candidates.get(select.value);
            const market = model?.market_context;
            if (!model) {
                contextHint.textContent = "";
                return;
            }
            if (!market) {
                contextHint.textContent = "This older candidate has no market context. Retrain it before comparison.";
                return;
            }
            document.getElementById("btSymbol").value = market.symbol;
            const timeframe = document.getElementById("btTimeframe");
            if (![...timeframe.options].some(option => option.value === market.timeframe)) {
                timeframe.add(new Option(market.timeframe, market.timeframe));
            }
            timeframe.value = market.timeframe;
            contextHint.textContent = `Backtest symbol and timeframe set to ${market.symbol} / ${market.timeframe} to match this candidate.`;
        });
        selectRequestedCandidate(select, candidates, contextHint);
        updateCandidateComparisonAvailability();
    }
    catch (error) {
        console.warn("Candidate comparison models unavailable:", error);
    }
}

function selectRequestedCandidate(select, candidates, contextHint) {
    if (!requestedCandidateId || !candidates.has(requestedCandidateId)) return;
    select.value = requestedCandidateId;
    const aiStrategy = [...strategiesById.entries()]
        .find(([, strategy]) => strategy.strategy_type === "AI_ASSISTED_XGB");
    if (aiStrategy) document.getElementById("btStrategy").value = aiStrategy[0];
    select.dispatchEvent(new Event("change"));
    contextHint.textContent = `${contextHint.textContent} Review the settings, then explicitly run the backtest.`;
}

function updateCandidateComparisonAvailability() {

    const strategy = strategiesById.get(document.getElementById("btStrategy").value);
    const candidateSelect = document.getElementById("btCandidateModel");
    const contextHint = document.getElementById("btCandidateModelContext");
    const supported = strategy?.strategy_type === "AI_ASSISTED_XGB";

    candidateSelect.disabled = !supported;

    if (!supported) {
        candidateSelect.value = "";
        contextHint.textContent = "Candidate comparison is available only for an AI Assisted XGBoost strategy.";
    }
    else if (!candidateSelect.value) {
        contextHint.textContent = "Select a candidate to compare it with the compatible champion.";
    }
}

initializeBacktest();

async function loadPage() {
    await loadStrategies();
    await loadCandidateModels();
}

loadPage();

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
