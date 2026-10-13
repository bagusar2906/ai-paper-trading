import { adjustFunds } from "../api.js";


export function initializeFundAdjustment() {

    document.getElementById("btnSaveFunds").addEventListener(
        "click",
        submitFundAdjustment,
    );

}


async function submitFundAdjustment() {

    const input = document.getElementById("fundAdjustmentAmount");
    const amount = Number(input.value);

    if (!Number.isFinite(amount) || amount === 0) {
        alert("Enter a non-zero deposit or withdrawal amount.");
        return;
    }

    try {
        await adjustFunds(amount);
        bootstrap.Modal.getInstance(document.getElementById("fundsModal"))?.hide();
        input.value = "";
        window.dispatchEvent(new Event("dashboard-refresh"));
    }
    catch (error) {
        alert(`Unable to adjust funds: ${error.message}`);
    }

}
