export function updateActiveStrategy(strategy) {

    const element = document.getElementById("activeStrategy");

    if (!strategy) {
        element.className = "badge text-bg-warning";
        element.textContent = "No active strategy";
        return;
    }

    element.className = "badge text-bg-success";
    element.textContent = `${strategy.name} (${strategy.strategy_type})`;

}
