import { deleteModel, getModelImprovementReport, getModels, promoteModel, rollbackModel, trainCandidate } from "../api.js";

let pendingReview = null;
let pendingDeletion = null;

export function initializeModelOperations() {
    const submitButton = document.getElementById("submitCandidateTraining");
    if (submitButton) submitButton.addEventListener("click", () => train(submitButton));

    const reviewButton = document.getElementById("submitModelReview");
    if (reviewButton) reviewButton.addEventListener("click", () => submitReview(reviewButton));

    const deleteButton = document.getElementById("submitModelDelete");
    if (deleteButton) deleteButton.addEventListener("click", () => submitDeletion(deleteButton));
}

export async function refreshModelOperations() {
    const body = document.querySelector("#modelOperations tbody");
    const status = document.getElementById("modelOperationsStatus");
    if (!body) return;
    try {
        const [models, report] = await Promise.all([getModels(), getModelImprovementReport()]);
        body.replaceChildren(...models.map(model => row(model)));
        renderImprovementReport(report);
        status.textContent = models.some(model => model.status === "champion") ? "Paper-only champion available" : "No champion — AI strategy will hold";
    } catch (error) {
        status.textContent = `Model status unavailable: ${error.message}`;
    }
}

function renderImprovementReport(report) {
    const container = document.getElementById("modelImprovementReport");
    if (!container) return;
    container.replaceChildren();
    const assessments = report.assessments || [];
    if (!assessments.length) {
        container.textContent = "Train a candidate to receive a read-only improvement recommendation.";
        return;
    }
    for (const assessment of assessments) {
        const item = document.createElement("div");
        item.className = "border rounded p-2 mb-2 small";
        const heading = document.createElement("strong");
        heading.textContent = `${assessment.candidate_model_id}: ${assessment.recommendation === "paper_test" ? "Paper-test recommended" : "Investigate before paper testing"}`;
        const comparison = document.createElement("div");
        comparison.className = "text-muted";
        const auc = assessment.deltas?.roc_auc;
        const brier = assessment.deltas?.brier_score;
        comparison.textContent = assessment.champion_model_id
            ? `Champion: ${assessment.champion_model_id} · Δ ROC AUC: ${formatDelta(auc)} · Δ Brier: ${formatDelta(brier)}`
            : "No compatible champion for comparison.";
        const reasons = document.createElement("ul");
        reasons.className = "mb-0 mt-1 ps-3";
        for (const reason of assessment.reasons || []) {
            const reasonItem = document.createElement("li");
            reasonItem.textContent = reason;
            reasons.append(reasonItem);
        }
        item.append(heading, comparison, reasons);
        container.append(item);
    }
}

function formatDelta(value) {
    return Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(3)}` : "—";
}

function row(model) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${model.model_id}</td><td><span class="badge text-bg-${model.status === "champion" ? "success" : "secondary"}">${model.status}</span></td><td>${model.feature_set_id}</td><td>${model.label_definition_id}</td><td>${formatMetrics(model.metrics)}</td><td></td>`;
    const actions = tr.lastElementChild;
    if (model.status === "candidate" || model.status === "retired") {
        const button = document.createElement("button");
        button.className = "btn btn-sm btn-outline-primary";
        button.textContent = model.status === "candidate" ? "Promote" : "Rollback";
        button.onclick = () => openReviewDialog(model);
        actions.append(button);

        const deleteButton = document.createElement("button");
        deleteButton.className = "btn btn-sm btn-outline-danger ms-1";
        deleteButton.textContent = "Delete";
        deleteButton.onclick = () => openDeleteDialog(model);
        actions.append(deleteButton);
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

function openReviewDialog(model) {
    pendingReview = model;
    const action = model.status === "candidate" ? "Promote" : "Roll back";
    document.getElementById("modelReviewTitle").textContent = `${action} Model`;
    document.getElementById("modelReviewDescription").textContent = `${action} ${model.model_id}. This action is paper-only and will be recorded in the audit history.`;
    document.getElementById("modelReviewReviewer").value = "";
    document.getElementById("modelReviewRationale").value = "";
    document.getElementById("modelReviewStatus").textContent = "";
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modelReviewModal")).show();
}

async function submitReview(button) {
    if (!pendingReview) return;
    const reviewer = document.getElementById("modelReviewReviewer").value.trim();
    const rationale = document.getElementById("modelReviewRationale").value.trim();
    const status = document.getElementById("modelReviewStatus");
    if (!reviewer || !rationale) {
        status.textContent = "Reviewer and rationale are required.";
        return;
    }
    button.disabled = true;
    try {
        if (pendingReview.status === "candidate") await promoteModel(pendingReview.model_id, reviewer, rationale);
        else await rollbackModel(pendingReview.model_id, reviewer, rationale);
        await refreshModelOperations();
        bootstrap.Modal.getInstance(document.getElementById("modelReviewModal"))?.hide();
        pendingReview = null;
    } catch (error) {
        status.textContent = `Model operation failed: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}

async function train(button) {
    const bars = document.getElementById("candidateBars");
    const horizon = document.getElementById("candidateHorizon");
    const threshold = document.getElementById("candidateThreshold");
    const status = document.getElementById("candidateTrainingStatus");
    const dialog = document.getElementById("trainCandidateModal");
    if (!bars || !horizon || !threshold || !status || !dialog) return;
    button.disabled = true;
    setTrainingStatus(status, "info", "Training paper-only candidate from completed candles…");
    try {
        const result = await trainCandidate({
            bars: Number(bars.value),
            horizon_candles: Number(horizon.value),
            up_return_threshold: Number(threshold.value),
        });
        if (result.status === "duplicate") {
            setTrainingStatus(status, "warning", `⚠ Training skipped: ${result.message}`);
            return;
        }
        await refreshModelOperations();
        document.getElementById("modelOperationsStatus").textContent = `Candidate ${result.model_id} trained on ${result.training_rows} rows; review before promotion.`;
        bootstrap.Modal.getOrCreateInstance(dialog).hide();
    } catch (error) {
        setTrainingStatus(status, "danger", `Candidate training failed: ${error.message}`);
    } finally {
        button.disabled = false;
    }
}

function setTrainingStatus(element, variant, message) {
    element.className = `alert alert-${variant} small mt-3 mb-0 py-2`;
    element.textContent = message;
}

function openDeleteDialog(model) {
    pendingDeletion = model;
    document.getElementById("modelDeleteDescription").textContent = `Delete ${model.model_id}? This permanently removes the candidate/retired registry entry and its managed local artifacts.`;
    document.getElementById("modelDeleteReviewer").value = "";
    document.getElementById("modelDeleteRationale").value = "";
    document.getElementById("modelDeleteStatus").textContent = "";
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modelDeleteModal")).show();
}

async function submitDeletion(button) {
    if (!pendingDeletion) return;
    const reviewer = document.getElementById("modelDeleteReviewer").value.trim();
    const rationale = document.getElementById("modelDeleteRationale").value.trim();
    const status = document.getElementById("modelDeleteStatus");
    if (!reviewer || !rationale) {
        status.textContent = "Reviewer and deletion rationale are required.";
        return;
    }
    button.disabled = true;
    try {
        await deleteModel(pendingDeletion.model_id, reviewer, rationale);
        await refreshModelOperations();
        bootstrap.Modal.getInstance(document.getElementById("modelDeleteModal"))?.hide();
        pendingDeletion = null;
    } catch (error) {
        status.textContent = `Model deletion failed: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}
