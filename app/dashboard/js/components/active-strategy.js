export function updateActiveStrategy(strategy) {

    const element = document.getElementById("activeStrategy");
    const riskSettings = document.getElementById("strategyRiskSettings");

    if (!strategy) {
        element.className = "badge text-bg-warning";
        element.textContent = "No active strategy";
        riskSettings.textContent = "";
        return;
    }

    element.className = "badge text-bg-success";
    element.textContent = `${strategy.name} (${strategy.strategy_type})`;

    if (
        strategy.stop_loss_pips != null
        && strategy.take_profit_pips != null
        && strategy.risk_reward_ratio != null
    ) {
        riskSettings.textContent =
            `Strategy SL: ${strategy.stop_loss_pips} pips · `
            + `TP: ${strategy.take_profit_pips} pips · `
            + `R:R 1:${strategy.risk_reward_ratio}`;
    }
    else {
        riskSettings.textContent = "Strategy does not define fixed SL/TP.";
    }

}
