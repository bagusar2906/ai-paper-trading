import {
    getSettings,
    updateSettings
} from "../api.js";

export async function initializeTradingMode() {

    const select =
        document.getElementById("tradingMode");

    let previousValue = select.value;

    try {

        const settings =
            await getSettings();

        select.value =
            settings.trading_mode;

        previousValue = select.value;

        updateManualOrderAvailability(select.value);

    }
    catch (error) {

        console.error(
            "Failed to load trading mode",
            error
        );

    }

    select.addEventListener(
        "change",
        async () => {

            const newValue = select.value;

            try {

                await updateSettings({

                    trading_mode: newValue

                });

                previousValue = newValue;

                updateManualOrderAvailability(newValue);

            }
            catch (error) {

                console.error(
                    "Failed to update trading mode",
                    error
                );

                select.value = previousValue;

                alert(
                    "Unable to update trading mode. Please try again."
                );

            }

        });

}

function updateManualOrderAvailability(mode) {

    const button = document.getElementById("btnNewOrder");
    const isAuto = mode === "AUTO";

    button.disabled = isAuto;
    button.title = isAuto
        ? "Manual orders are disabled while auto trading is active."
        : "Place a manual order";

    if (isAuto) {
        bootstrap.Modal.getInstance(
            document.getElementById("orderModal")
        )?.hide();
    }

}
