export function updateSignals(signals) {

    const tbody =
        document.querySelector("#signals tbody");

    if (!tbody)
        return;

    tbody.innerHTML = "";

    signals.forEach(signal => {

        tbody.innerHTML += `
        <tr>
            <td>${new Date(signal.time).toLocaleString()}</td>
            <td>${signal.symbol}</td>
            <td>${signal.action}</td>
            <td>${signal.price.toFixed(2)}</td>
            <td>${(signal.confidence * 100).toFixed(1)}%</td>
        </tr>
        `;

    });

}