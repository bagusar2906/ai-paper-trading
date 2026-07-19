async function loadDashboard() {

    const response = await fetch("/dashboard");

    const data = await response.json();

    document.getElementById("dashboard").innerHTML =
        `
        <h4>Balance : ${data.account.balance}</h4>

        <h4>Equity : ${data.account.equity}</h4>

        <h4>Open Positions : ${data.positions.length}</h4>

        <h4>Trades : ${data.trades.length}</h4>
        `;
}

loadDashboard();

setInterval(loadDashboard, 2000);