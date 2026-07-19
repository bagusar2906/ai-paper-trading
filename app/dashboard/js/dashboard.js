async function refreshDashboard() {

    const response = await fetch("/dashboard");

    const data = await response.json();

    document.getElementById("balance").innerText =
        data.account.balance.toFixed(2);

    document.getElementById("equity").innerText =
        data.account.equity.toFixed(2);

    document.getElementById("floating").innerText =
        data.account.floating_pnl.toFixed(2);

    document.getElementById("positionCount").innerText =
        data.positions.length;

    const tbody =
        document.querySelector("#positionsTable tbody");

    tbody.innerHTML = "";

    data.positions.forEach(position => {

        tbody.innerHTML += `
        <tr>
            <td>${position.symbol}</td>
            <td>${position.side}</td>
            <td>${position.entry_price}</td>
            <td>${position.stop_loss}</td>
            <td>${position.take_profit}</td>
        </tr>`;
    });

}

refreshDashboard();

setInterval(refreshDashboard, 2000);