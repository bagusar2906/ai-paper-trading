import { initializeModelOperations, refreshModelOperations } from "./components/model-operations.js";
import { askModelLab, runModelMonitoringCheck } from "./api.js";

async function submitModelLabQuestion() {
    const question = document.getElementById("modelLabQuestion");
    const answer = document.getElementById("modelLabAnswer");
    const button = document.getElementById("askModelLab");
    if (!question.value.trim()) return;
    button.disabled = true;
    answer.textContent = "Reviewing registry evidence…";
    try {
        const result = await askModelLab(question.value.trim());
        answer.textContent = `${result.answer} Source: ${result.source.replaceAll("_", " ")}.`;
    } catch (error) {
        answer.textContent = `Assistant unavailable: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}

async function recordMonitoringCheck() {
    const button = document.getElementById("recordMonitoringCheck");
    const status = document.getElementById("monitoringCheckStatus");
    button.disabled = true;
    status.textContent = "Recording a read-only monitoring recommendation…";
    try {
        const result = await runModelMonitoringCheck();
        status.textContent = `Recorded: ${result.recommendation || result.status}. No retraining was started.`;
        await refreshModelOperations();
    } catch (error) {
        status.textContent = `Monitoring check unavailable: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    initializeModelOperations();
    document.getElementById("askModelLab").addEventListener("click", submitModelLabQuestion);
    document.getElementById("recordMonitoringCheck").addEventListener("click", recordMonitoringCheck);
    document.getElementById("modelLabQuestion").addEventListener("keydown", (event) => {
        if (event.key === "Enter") submitModelLabQuestion();
    });
    await refreshModelOperations();
    setInterval(refreshModelOperations, 30000);
});
