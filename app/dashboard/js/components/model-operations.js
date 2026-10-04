import { getModels, promoteModel, rollbackModel, trainCandidate } from "../api.js";

export function initializeModelOperations() {
    const button = document.getElementById("trainCandidate");
    if (button) button.addEventListener("click", () => train(button));
}

export async function refreshModelOperations() {
    const body = document.querySelector("#modelOperations tbody");
    const status = document.getElementById("modelOperationsStatus");
    if (!body) return;
    try {
        const models = await getModels();
        body.replaceChildren(...models.map(model => row(model)));
        status.textContent = models.some(model => model.status === "champion") ? "Paper-only champion available" : "No champion — AI strategy will hold";
    } catch (error) {
        status.textContent = `Model status unavailable: ${error.message}`;
    }
}

function row(model) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${model.model_id}</td><td><span class="badge text-bg-${model.status === "champion" ? "success" : "secondary"}">${model.status}</span></td><td>${model.feature_set_id}</td><td>${model.label_definition_id}</td><td>${formatMetrics(model.metrics)}</td><td></td>`;
    const actions = tr.lastElementChild;
    if (model.status === "candidate" || model.status === "retired") {
        const button = document.createElement("button");
        button.className = "btn btn-sm btn-outline-primary";
        button.textContent = model.status === "candidate" ? "Promote" : "Rollback";
        button.onclick = () => operate(model, button);
        actions.append(button);
    }
    return tr;
}

function formatMetrics(metrics = {}) {
    const values = [
        ["Precision", metrics.precision],
        ["Recall", metrics.recall],
        ["ROC AUC", metrics.roc_auc],
        ["Brier", metrics.brier_score],
    ].filter(([, value]) => Number.isFinite(value));
    return values.length
        ? values.map(([name, value]) => `${name}: ${value.toFixed(3)}`).join(" · ")
        : "—";
}

async function operate(model, button) {
    const reviewer = window.prompt("Reviewer name (required):");
    const rationale = window.prompt("Rationale (required):");
    if (!reviewer || !rationale) return;
    button.disabled = true;
    try {
        if (model.status === "candidate") await promoteModel(model.model_id, reviewer, rationale);
        else await rollbackModel(model.model_id, reviewer, rationale);
        await refreshModelOperations();
    } catch (error) {
        window.alert(`Model operation failed: ${error.message}`);
        button.disabled = false;
    }
}

async function train(button) {
    const bars = window.prompt("Completed candles to train on (250–5000):", "1000");
    if (bars === null) return;
    const horizon = window.prompt("Prediction horizon in candles:", "12");
    if (horizon === null) return;
    const threshold = window.prompt("Up-return threshold (for example, 0.003 = 0.3%):", "0.003");
    if (threshold === null) return;

    const status = document.getElementById("modelOperationsStatus");
    button.disabled = true;
    status.textContent = "Training paper-only candidate from completed candles…";
    try {
        const result = await trainCandidate({
            bars: Number(bars),
            horizon_candles: Number(horizon),
            up_return_threshold: Number(threshold),
        });
        await refreshModelOperations();
        status.textContent = `Candidate ${result.model_id} trained on ${result.training_rows} rows; review before promotion.`;
    } catch (error) {
        status.textContent = `Candidate training failed: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}
