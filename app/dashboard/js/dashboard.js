async function loadDashboard() {

    const response = await fetch("/dashboard");
    const data = await response.json();

    document.getElementById("balance").innerText =
        data.account.balance.toFixed(2);

    document.getElementById("equity").innerText =
        data.account.equity.toFixed(2);

    document.getElementById("floating").innerText =
        data.account.floating_pnl.toFixed(2);
}

loadDashboard();

setInterval(loadDashboard, 2000);