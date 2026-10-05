import { initializeModelOperations, refreshModelOperations } from "./components/model-operations.js";
import { askModelLab, runModelMonitoringCheck } from "./api.js";

function appendModelLabMessage(role, text, { pending = false, source = "" } = {}) {
    const messages = document.getElementById("modelLabMessages");
    const message = document.createElement("div");
    message.className = `model-lab-message model-lab-${role}`;
    if (pending) message.dataset.pending = "true";

    if (role === "assistant") {
        const avatar = document.createElement("span");
        avatar.className = "model-lab-avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = "AI";
        message.append(avatar);
    }

    const bubble = document.createElement("div");
    bubble.className = "model-lab-bubble";
    const content = document.createElement("div");
    content.className = "model-lab-content";
    text.split(/\n{2,}/).forEach((paragraph) => {
        const element = document.createElement("p");
        element.textContent = paragraph;
        content.append(element);
    });
    bubble.append(content);
    if (source) {
        const detail = document.createElement("div");
        detail.className = "model-lab-source";
        detail.textContent = source === "omniroute" ? "Answered by AI via OmniRoute" : "Answered from local registry evidence";
        bubble.append(detail);
    }
    message.append(bubble);
    messages.append(message);
    messages.scrollTop = messages.scrollHeight;
    return message;
}

async function submitModelLabQuestion() {
    const question = document.getElementById("modelLabQuestion");
    const button = document.getElementById("askModelLab");
    const text = question.value.trim();
    if (!text) return;
    button.disabled = true;
    question.disabled = true;
    appendModelLabMessage("user", text);
    question.value = "";
    const pending = appendModelLabMessage("assistant", "Thinking…", { pending: true });
    try {
        const result = await askModelLab(text);
        pending.remove();
        appendModelLabMessage("assistant", result.answer, { source: result.source });
    } catch (error) {
        pending.remove();
        appendModelLabMessage("assistant", `I couldn’t answer that right now: ${error.message}`);
    } finally {
        button.disabled = false;
        question.disabled = false;
        question.focus();
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
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submitModelLabQuestion();
        }
    });
    document.querySelectorAll(".model-lab-suggestion").forEach((button) => {
        button.addEventListener("click", () => {
            document.getElementById("modelLabQuestion").value = button.dataset.question;
            submitModelLabQuestion();
        });
    });
    await refreshModelOperations();
    setInterval(refreshModelOperations, 30000);
});
