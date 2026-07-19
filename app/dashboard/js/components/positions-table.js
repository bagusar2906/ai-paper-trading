export function updatePositions(positions) {

    const tbody =
        document.querySelector("#positionsTable tbody");

    if (!tbody)
        return;

    tbody.innerHTML = "";

    positions.forEach(position => {

        tbody.innerHTML += `
        <tr>
            <td>${position.symbol}</td>
            <td>${position.side}</td>
            <td>${position.entry_price.toFixed(2)}</td>
            <td>${position.stop_loss.toFixed(2)}</td>
            <td>${position.take_profit.toFixed(2)}</td>
        </tr>
        `;

    });

    document.getElementById("positionCount").textContent =
        positions.length;
}