export function updateCurrentSignal(signal) {

    const label = document.getElementById("currentSignal");

    if (!label)
        return;

    if (!signal) {

        label.textContent = "-";

        return;
    }

    label.textContent =
        `${signal.action} @ ${signal.price.toFixed(2)}`;
}