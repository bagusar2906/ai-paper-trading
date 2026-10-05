import { deleteModel, getActiveSignalModel, getModelExperimentPlan, getModelHealth, getModelImprovementReport, getModelReviewGuidance, getModelReviewHistory, getModels, promoteModel, rollbackModel, trainCandidate } from "../api.js";

let pendingReview = null;
let pendingDeletion = null;

export function initializeModelOperations() {
    const submitButton = document.getElementById("submitCandidateTraining");
    if (submitButton) submitButton.addEventListener("click", () => train(submitButton));

    const reviewButton = document.getElementById("submitModelReview");
    if (reviewButton) reviewButton.addEventListener("click", () => submitReview(reviewButton));

    const guidanceButton = document.getElementById("requestModelReviewGuidance");
    if (guidanceButton) guidanceButton.addEventListener("click", () => requestReviewGuidance(guidanceButton));

    const deleteButton = document.getElementById("submitModelDelete");
    if (deleteButton) deleteButton.addEventListener("click", () => submitDeletion(deleteButton));

    const planButton = document.getElementById("planExperiments");
    if (planButton) planButton.addEventListener("click", () => planExperiments(planButton));
}

async function planExperiments(button) {
    const status = document.getElementById("modelExperimentStatus");
    const parameters = trainingParameters();
    button.disabled = true;
    try {
        const plan = await getModelExperimentPlan(parameters);
        renderExperimentPlan(plan);
        status.textContent = "Suggestions are read-only. Choose one to copy its settings into the training form.";
    } catch (error) {
        status.textContent = `Could not create experiment plan: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}

function renderExperimentPlan(plan) {
    const container = document.getElementById("modelExperimentPlan");
    if (!container) return;
    container.replaceChildren();
    for (const experiment of plan.experiments || []) {
        const item = document.createElement("div");
        item.className = "border rounded p-2 mb-2 small";
        const title = document.createElement("strong");
        title.textContent = experiment.id;
        const rationale = document.createElement("div");
        rationale.className = "text-muted mb-1";
        rationale.textContent = experiment.rationale;
        const button = document.createElement("button");
        button.className = "btn btn-sm btn-outline-primary";
        button.textContent = "Use settings";
        button.onclick = () => applyExperiment(experiment.parameters);
        item.append(title, rationale, button);
        container.append(item);
    }
}

function applyExperiment(parameters) {
    for (const [key, value] of Object.entries(parameters)) {
        const input = document.getElementById(trainingFieldId(key));
        if (input) input.value = value;
    }
    bootstrap.Modal.getOrCreateInstance(document.getElementById("trainCandidateModal")).show();
}

function trainingParameters() {
    const names = ["bars", "horizon_candles", "up_return_threshold", "n_estimators", "max_depth", "learning_rate", "probability_threshold"];
    return Object.fromEntries(names.map(name => {
        const input = document.getElementById(trainingFieldId(name));
        return [name, Number(input?.value)];
    }));
}

function trainingFieldId(name) {
    const specialIds = {
        horizon_candles: "candidateHorizon",
        up_return_threshold: "candidateThreshold",
    };
    return specialIds[name] || `candidate${name.split("_").map(word => word[0].toUpperCase() + word.slice(1)).join("")}`;
}

export async function refreshModelOperations() {
    const body = document.querySelector("#modelOperations tbody");
    const status = document.getElementById("modelOperationsStatus");
    if (!body) return;
    try {
        const [models, report, health, signalModel] = await Promise.all([getModels(), getModelImprovementReport(), getModelHealth(), getActiveSignalModel()]);
        body.replaceChildren(...models.map(model => row(model, signalModel)));
        renderImprovementReport(report);
        renderModelHealth(health);
        renderSignalModel(signalModel);
        status.textContent = signalModel.signal_ready ? "Paper-only signal model available" : "No compatible signal model — AI strategy will hold";
    } catch (error) {
        status.textContent = `Model status unavailable: ${error.message}`;
    }
}

function renderSignalModel(signalModel) {
    const target = document.getElementById("activeSignalModel");
    if (!target) return;
    if (!signalModel.signal_ready) {
        target.textContent = `Not ready: ${signalModel.reason || "No compatible champion is available."}`;
        return;
    }
    target.textContent = `Active for signals: ${signalModel.champion_model_id} · ${signalModel.symbol} ${signalModel.timeframe} · ${signalModel.label_definition_id}`;
}

function renderModelHealth(health) {
    const target = document.getElementById("modelHealth");
    if (!target) return;
    const label = health.status === "healthy" ? "Healthy" : health.status === "watch" ? "Watch" : health.status === "stale" ? "Retraining review" : "Unavailable";
    const drift = (health.top_drift || []).map(item => `${item.feature}: ${item.score.toFixed(1)} IQR`).join(" · ");
    target.replaceChildren();
    const summary = document.createElement("span");
    summary.textContent = `${label}: ${health.reasons?.[0] || "No health detail available."}${drift ? ` Top drift: ${drift}` : ""}`;
    target.append(summary);
    if (["plan_retraining", "retrain_required"].includes(health.recommendation)) {
        const button = document.createElement("button");
        button.className = "btn btn-sm btn-outline-primary ms-2";
        button.textContent = "Retrain as candidate";
        button.title = "Opens training with a new candidate; the champion remains unchanged.";
        button.onclick = () => {
            bootstrap.Modal.getOrCreateInstance(document.getElementById("trainCandidateModal")).show();
        };
        target.append(button);
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
        heading.textContent = `#${assessment.rank} ${assessment.candidate_model_id}: ${assessment.recommendation === "paper_test" ? "Paper-test recommended" : "Investigate before paper testing"}`;
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
        if (assessment.comparison_available || assessment.champion_model_id) {
            const compareButton = document.createElement("button");
            compareButton.className = "btn btn-sm btn-outline-secondary mt-2";
            compareButton.textContent = "Compare in backtest";
            compareButton.onclick = () => {
                window.location.href = `backtest.html?candidate_model_id=${encodeURIComponent(assessment.candidate_model_id)}`;
            };
            item.append(heading, comparison, reasons, compareButton);
        } else {
            const unavailable = document.createElement("div");
            unavailable.className = "text-muted mt-2";
            unavailable.textContent = "Backtest comparison is unavailable until a compatible champion exists.";
            item.append(heading, comparison, reasons, unavailable);
        }
        container.append(item);
    }
}

function formatDelta(value) {
    return Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(3)}` : "—";
}

function row(model, signalModel) {
    const tr = document.createElement("tr");
    const activeForSignals = signalModel.signal_ready && signalModel.champion_model_id === model.model_id;
    tr.innerHTML = `<td>${model.model_id}</td><td><span class="badge text-bg-${model.status === "champion" ? "success" : "secondary"}">${model.status}</span></td><td>${formatMarketContext(model.market_context)}</td><td>${model.feature_set_id}</td><td>${model.label_definition_id}</td><td>${activeForSignals ? '<span class="badge text-bg-primary">Active</span>' : "—"}</td><td>${formatMetrics(model.metrics)}</td><td>${formatFeatureImportance(model.feature_importance)}</td><td></td>`;
    const actions = tr.lastElementChild;
    if (model.status === "candidate" || model.status === "retired") {
        const button = document.createElement("button");
        button.className = "btn btn-sm btn-outline-primary";
        button.textContent = model.status === "candidate" ? "Promote" : "Rollback";
        button.onclick = () => openReviewDialog(model);
        actions.append(button);

    }
    const deleteButton = document.createElement("button");
    deleteButton.className = "btn btn-sm btn-outline-danger ms-1";
    deleteButton.textContent = "Delete";
    deleteButton.onclick = () => openDeleteDialog(model);
    actions.append(deleteButton);
    const historyButton = document.createElement("button");
    historyButton.className = "btn btn-sm btn-outline-secondary ms-1";
    historyButton.textContent = "History";
    historyButton.onclick = () => openReviewHistory(model);
    actions.append(historyButton);
    return tr;
}

function formatMarketContext(context) {
    return context?.symbol && context?.timeframe ? `${context.symbol} · ${context.timeframe}` : "—";
}

async function openReviewHistory(model) {
    const body = document.getElementById("modelReviewHistoryBody");
    if (!body) return;
    body.textContent = "Loading review history…";
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modelReviewHistoryModal")).show();
    try {
        const history = await getModelReviewHistory(model.model_id);
        body.replaceChildren();
        if (!history.length) {
            body.textContent = "No saved review events yet.";
            return;
        }
        for (const event of history.slice().reverse()) {
            const item = document.createElement("div");
            item.className = "border rounded p-2 mb-2 small";
            item.textContent = `${event.recorded_at} · ${event.type} · ${JSON.stringify(event.evidence)}`;
            body.append(item);
        }
    } catch (error) {
        body.textContent = `Could not load review history: ${error.message}`;
    }
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

function formatFeatureImportance(features = []) {
    return features.length
        ? features.map(item => `${item.feature}: ${item.importance.toFixed(3)}`).join(" · ")
        : "—";
}

function openReviewDialog(model) {
    pendingReview = model;
    const action = model.status === "candidate" ? "Promote" : "Roll back";
    document.getElementById("modelReviewTitle").textContent = `${action} Model`;
    document.getElementById("modelReviewDescription").textContent = `${action} ${model.model_id}. This action is paper-only and will be recorded in the audit history.`;
    document.getElementById("modelReviewReviewer").value = "";
    document.getElementById("modelReviewRationale").value = "";
    document.getElementById("modelReviewGuidance").textContent = "";
    document.getElementById("modelReviewStatus").textContent = "";
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modelReviewModal")).show();
}

async function requestReviewGuidance(button) {
    if (!pendingReview) return;
    const target = document.getElementById("modelReviewGuidance");
    button.disabled = true;
    target.textContent = "Preparing read-only AI guidance…";
    try {
        const result = await getModelReviewGuidance(pendingReview.model_id);
        target.textContent = `AI recommendation: ${result.recommendation}. Guidance (${result.source}): ${result.guidance}`;
    } catch (error) {
        target.textContent = `AI guidance unavailable: ${error.message}`;
    } finally {
        button.disabled = false;
    }
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
    const parameters = trainingParameters();
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
            n_estimators: parameters.n_estimators,
            max_depth: parameters.max_depth,
            learning_rate: parameters.learning_rate,
            probability_threshold: parameters.probability_threshold,
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
    const impact = model.status === "champion"
        ? "This champion will immediately stop being available for future AI-assisted signals."
        : "This model is not used for current AI-assisted signals.";
    document.getElementById("modelDeleteDescription").textContent = `Delete ${model.model_id}? ${impact} This permanently removes the registry entry and its managed local artifacts.`;
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
