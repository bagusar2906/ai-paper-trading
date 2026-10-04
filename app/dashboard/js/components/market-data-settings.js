import { getSettings, updateSettings } from "../api.js";

export async function initializeMarketDataSettings() {
    const select = document.getElementById("marketDataProvider");
    const saveButton = document.getElementById("saveMarketDataProvider");
    const status = document.getElementById("marketDataProviderStatus");
    const dialog = document.getElementById("marketDataSettingsModal");
    if (!select || !saveButton || !status || !dialog) return;

    try {
        const settings = await getSettings();
        select.value = settings.market_data_provider;
        status.textContent = `Current source: ${select.options[select.selectedIndex].text}.`;
    } catch (error) {
        status.textContent = `Unable to load data source: ${error.message}`;
    }

    saveButton.addEventListener("click", async () => {
        saveButton.disabled = true;
        try {
            const settings = await updateSettings({ market_data_provider: select.value });
            select.value = settings.market_data_provider;
            status.textContent = `Saved. New requests will use ${select.options[select.selectedIndex].text}.`;
            bootstrap.Modal.getOrCreateInstance(dialog).hide();
        } catch (error) {
            status.textContent = `Unable to save data source: ${error.message}`;
        } finally {
            saveButton.disabled = false;
        }
    });
}
