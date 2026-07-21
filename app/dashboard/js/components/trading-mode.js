import {
    getSettings,
    updateSettings
} from "../api.js";

export async function initializeTradingMode() {

    const select =
        document.getElementById("tradingMode");

    const settings =
        await getSettings();

    select.value =
        settings.trading_mode;

    select.addEventListener(
        "change",
        async () => {

            await updateSettings({

                trading_mode: select.value

            });

        });

}