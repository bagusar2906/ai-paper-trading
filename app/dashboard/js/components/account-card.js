export function updateAccount(account) {

    document.getElementById("balance").textContent =
        account.balance.toFixed(2);

    document.getElementById("equity").textContent =
        account.equity.toFixed(2);

    document.getElementById("margin").textContent =
        account.margin.toFixed(2);

    document.getElementById("freeMargin").textContent =
        account.free_margin.toFixed(2);

    document.getElementById("floatingPnL").textContent =
        account.floating_pnl.toFixed(2);
}