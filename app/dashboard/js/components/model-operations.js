import { deleteModel, getActiveSignalModel, getModelExperimentPlan, getModelHealth, getModelImprovementReport, getModelReviewGuidance, getModelReviewHistory, getModels, promoteModel, rollbackModel, trainCandidate } from "../api.js";
import { configureSelfTraining, getSelfTrainingStatus } from "../api.js";
import { analyzeModel } from "../api.js";
import { getModelLabDataSource, setModelLabDataSource } from "../api.js";
import { getModelTrainingSettings, saveModelTrainingSettings } from "../api.js";

let pendingReview = null;
let pendingDeletion = null;
let analysisRequest = 0;
let modelDataSourcePending = false;
let modelDataSourceTask = null;
let trainingSettingsPending = false;
let trainingFormEdited = false;
let selectedTrainingModel = null;
const DATA_SOURCE_LABELS = {trading: "Trading app source", mt5: "MetaTrader 5", oanda: "OANDA", yahoo: "Yahoo Finance", twelve_data: "Twelve Data"};

export function initializeModelOperations() {
    modelDataSourceTask = initializeModelDataSource();
    const editSettings = document.getElementById("editTrainingSettings");
    if (editSettings) editSettings.addEventListener("click", () => openTrainingSettings(editSettings));
    const saveSettings = document.getElementById("saveTrainingSettings");
    if (saveSettings) saveSettings.addEventListener("click", () => saveTrainingSettings(saveSettings));
    document.getElementById("trainCandidate")?.addEventListener("click", () => {
        selectedTrainingModel = null;
        const title = document.getElementById("trainingSettingsTitle");
        if (title) title.textContent = "Train XGBoost Candidate";
        if (!trainingSettingsPending) disableTrainingSettings(false);
    });
    for (const id of trainingInputIds()) {
        const input = document.getElementById(id);
        input?.addEventListener("input", () => {trainingFormEdited = true;});
        input?.addEventListener("change", () => {trainingFormEdited = true;});
    }
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
    document.getElementById("enableSelfTraining")?.addEventListener("click", () => setSelfTraining(true));
    document.getElementById("disableSelfTraining")?.addEventListener("click", () => setSelfTraining(false));
    refreshSelfTraining(true);
}

async function initializeModelDataSource() {
    const select = document.getElementById("candidateDataSource");
    const status = document.getElementById("modelLabDataSourceStatus");
    if (!select || !status) return;
    modelDataSourcePending = true;
    select.disabled = true;
    const show = source => {status.textContent = `AI Model Lab source: ${DATA_SOURCE_LABELS[source] || source}. Use Save settings to store the setup; use Enable / update self-training to apply changes to background training.`;};
    try {
        const saved = await getModelLabDataSource();
        select.value = saved.data_source;
        show(saved.data_source);
    } catch (error) {
        status.textContent = `Could not load saved source: ${error.message}. Select a source before training.`;
    } finally {
        select.disabled = false;
        modelDataSourcePending = false;
    }
    select.addEventListener("change", async () => {
        modelDataSourcePending = true;
        select.disabled = true;
        try {
            modelDataSourceTask = setModelLabDataSource(select.value);
            const saved = await modelDataSourceTask;
            show(saved.data_source);
        } catch (error) {
            status.textContent = `Source preference was not saved: ${error.message}. New training still uses the selected source.`;
        } finally {
            select.disabled = false;
            modelDataSourcePending = false;
        }
    });
}

async function refreshSelfTraining(restoreConfig = false) {
    const target = document.getElementById("selfTrainingStatus");
    if (!target) return;
    try {
        const report = await getSelfTrainingStatus();
        showSelfTrainingStatus(report);
        if (restoreConfig && !trainingSettingsPending && !trainingFormEdited) restoreTrainingSettings(report.configuration);
    } catch (error) {
        target.textContent = `Self-training status unavailable: ${error.message}`;
    }
}

function restoreTrainingSettings(config, includeSource = false) {
    for (const [key, value] of Object.entries(config.training || {})) {
        if (key === "data_source" && !includeSource) continue;
        const input = document.getElementById(trainingFieldId(key));
        if (!input) continue;
        if (key === "replace_previous_candidate") input.checked = value;
        else input.value = value;
    }
    const interval = document.getElementById("selfTrainingInterval");
    if (interval) interval.value = config.interval_minutes;
}

function trainingInputIds() {
    const fields = ["bars", "horizon_candles", "up_return_threshold", "n_estimators", "max_depth", "learning_rate", "probability_threshold", "feature_set_id", "symbol", "timeframe", "data_source", "replace_previous_candidate"];
    return [...fields.map(trainingFieldId), "selfTrainingInterval"];
}

function disableTrainingSettings(disabled) {
    for (const id of [...trainingInputIds(), "saveTrainingSettings", "submitCandidateTraining", "enableSelfTraining"]) {
        const input = document.getElementById(id);
        if (input) input.disabled = disabled;
    }
}

async function openTrainingSettings(button, model = null) {
    const status = document.getElementById("candidateTrainingStatus");
    const dialog = document.getElementById("trainCandidateModal");
    if (!status || !dialog) return;
    if (trainingSettingsPending) return;
    selectedTrainingModel = model;
    const title = document.getElementById("trainingSettingsTitle");
    if (title) title.textContent = model ? `Edit settings: ${model.model_id}` : "Self-training settings";
    button.disabled = true;
    trainingSettingsPending = true;
    trainingFormEdited = true;
    disableTrainingSettings(true);
    setTrainingStatus(status, "info", "Loading saved training settings…");
    bootstrap.Modal.getOrCreateInstance(dialog).show();
    let loaded = false;
    try {
        if (modelDataSourceTask) await modelDataSourceTask.catch(() => {});
        disableTrainingSettings(true);
        const report = model ? await getModelTrainingSettings(model.model_id) : await getSelfTrainingStatus();
        restoreTrainingSettings(model ? report : report.configuration, true);
        loaded = true;
        if (!model) showSelfTrainingStatus(report);
        setTrainingStatus(status, "info", model ? `Editing ${model.model_id}. Save settings stores this model's retraining setup. Train Candidate uses these settings now; Enable / update self-training applies them to background training. ${(report.notes || []).join(' ')}` : "Edit any setting, then select Save settings. Training will not start when you save.");
    } catch (error) {
        setTrainingStatus(status, "danger", `Could not load saved settings: ${error.message}. Close and click ${model ? 'Edit settings' : 'Training settings'} to retry.`);
    } finally {
        trainingSettingsPending = false;
        disableTrainingSettings(!loaded);
        button.disabled = false;
    }
}

async function saveTrainingSettings(button) {
    const status = document.getElementById("candidateTrainingStatus");
    if (modelDataSourcePending || trainingSettingsPending) {
        setTrainingStatus(status, "info", "Wait for training settings and the data-source preference to finish loading or saving.");
        return;
    }
    button.disabled = true;
    trainingSettingsPending = true;
    disableTrainingSettings(true);
    const payload = {save_only: true, interval_minutes: Number(document.getElementById("selfTrainingInterval").value), training: trainingParameters()};
    try {
        if (selectedTrainingModel) {
            await saveModelTrainingSettings(selectedTrainingModel.model_id, {interval_minutes: payload.interval_minutes, training: payload.training});
            setTrainingStatus(status, "success", `Settings saved for ${selectedTrainingModel.model_id}. Train Candidate to retrain with these settings, or Enable / update self-training to use them for background training. Existing model predictions and scores stay unchanged until retraining.`);
        } else {
            const report = await configureSelfTraining(payload);
            showSelfTrainingStatus(report);
            const detail = report.configuration.enabled ? "Self-training remains enabled; new settings apply at the next scheduled check." : "Self-training remains off. Enable it when you are ready.";
            setTrainingStatus(status, "success", `Training settings saved. ${detail}${report.running ? " The current run can finish with its previous settings." : ''}`);
        }
    } catch (error) {
        setTrainingStatus(status, "danger", `Could not save training settings: ${error.message}`);
    } finally {
        trainingSettingsPending = false;
        disableTrainingSettings(false);
        button.disabled = false;
    }
}

function showSelfTrainingStatus(report) {
    const target = document.getElementById("selfTrainingStatus");
    if (!target) return;
    const config = report.configuration;
    const last = report.last_run || {};
    const labels = { candidate_created: 'New candidate trained', skipped_unchanged: 'Skipped: market data and settings are unchanged', failed: 'Last attempt failed', running: 'Training in progress', interrupted: 'Previous training was interrupted when the app closed' };
    const inputs = config.training?.feature_set_id === 'raw-ohlcv-v1' ? 'raw price and volume' : 'indicator inputs';
    const summary = config.enabled ? `Enabled: ${config.training.symbol} ${config.training.timeframe}, ${inputs}, every ${config.interval_minutes} minutes while the app backend is running. Source: ${DATA_SOURCE_LABELS[config.training.data_source || 'trading'] || config.training.data_source}.` : 'Self-training is off.';
    const progress = report.running ? ' Training in progress.' : last.status ? ` ${labels[last.status] || last.status}${last.model_id ? `: ${last.model_id}` : ''}.` : '';
    const sync = last.data_sync;
    const retention = config.training?.replace_previous_candidate !== false ? " Keeps the latest candidate per training setup." : " Keeps every trained candidate.";
    const replacement = last.replaced_model_ids?.length ? ` Replaced ${last.replaced_model_ids.length} previous candidate(s).` : '';
    const catchup = sync ? ` Data caught up: ${sync.downloaded_bars} new candles saved${sync.resumed_from ? `, resumed from ${new Date(sync.resumed_from).toLocaleString()}` : ''}. Last saved candle: ${new Date(sync.last_candle_at).toLocaleString()}. Training uses the latest ${sync.training_window_bars} candles.` : '';
    target.textContent = `${summary}${config.enabled ? retention : ''}${progress}${replacement}${catchup}${last.cleanup_warnings?.length ? ` ${last.cleanup_warnings.join(' ')}` : ''}${last.message ? ` ${last.message}` : ''}${config.enabled && last.next_check_at && !report.running ? ` Next check: ${new Date(last.next_check_at).toLocaleString()}.` : ''}`;
    const stop = document.getElementById("disableSelfTraining");
    if (stop) stop.disabled = !config.enabled;
    const summaryTarget = document.getElementById("trainingSettingsSummary");
    if (summaryTarget) summaryTarget.textContent = `${summary}${config.training?.bars ? ` Saved window: ${config.training.bars} candles.` : ''}${retention}`;
}

async function setSelfTraining(enabled) {
    const target = document.getElementById("selfTrainingStatus");
    if (enabled && modelDataSourcePending) {target.textContent = "Wait for the data-source preference to finish loading or saving."; return;}
    if (enabled && trainingSettingsPending) {target.textContent = "Wait for training settings to finish loading or saving."; return;}
    const button = document.getElementById(enabled ? "enableSelfTraining" : "disableSelfTraining");
    button.disabled = true;
    let updated = false;
    try {
        const payload = enabled ? { enabled, interval_minutes: Number(document.getElementById("selfTrainingInterval").value), training: trainingParameters() } : { enabled };
        showSelfTrainingStatus(await configureSelfTraining(payload));
        updated = true;
    } catch (error) {
        target.textContent = `Could not update self-training: ${error.message}`;
    } finally {
        button.disabled = !enabled && updated;
    }
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
    if (trainingSettingsPending) return;
    trainingFormEdited = true;
    for (const [key, value] of Object.entries(parameters)) {
        const input = document.getElementById(trainingFieldId(key));
        if (input) input.value = value;
    }
    bootstrap.Modal.getOrCreateInstance(document.getElementById("trainCandidateModal")).show();
}

function trainingParameters() {
    const names = ["bars", "horizon_candles", "up_return_threshold", "n_estimators", "max_depth", "learning_rate", "probability_threshold"];
    return {
        replace_previous_candidate: document.getElementById("candidateReplacePrevious")?.checked ?? true,
        data_source: document.getElementById("candidateDataSource")?.value || "trading",
        feature_set_id: document.getElementById("candidateFeatureSetId")?.value || "core-v1",
        symbol: document.getElementById("candidateSymbol")?.value || "XAUUSD",
        timeframe: document.getElementById("candidateTimeframe")?.value || "M5",
        ...Object.fromEntries(names.map(name => {
        const input = document.getElementById(trainingFieldId(name));
        return [name, Number(input?.value)];
    })) };
}

function trainingFieldId(name) {
    const specialIds = {
        data_source: "candidateDataSource",
        replace_previous_candidate: "candidateReplacePrevious",
        horizon_candles: "candidateHorizon",
        up_return_threshold: "candidateThreshold",
    };
    return specialIds[name] || `candidate${name.split("_").map(word => word[0].toUpperCase() + word.slice(1)).join("")}`;
}

export async function refreshModelOperations() {
    await refreshSelfTraining();
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
    if (signalModel.downside_ready === false) target.textContent += ` · ${signalModel.reason}`;
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
    const analyzeButton = document.createElement("button");
    analyzeButton.className = "btn btn-sm btn-outline-info me-1";
    analyzeButton.textContent = "Analyze";
    analyzeButton.onclick = async () => {
        analyzeButton.disabled = true;
        try { await openModelAnalysis(model); }
        finally { analyzeButton.disabled = false; }
    };
    actions.append(analyzeButton);
    const editSettings = document.createElement("button");
    editSettings.className = "btn btn-sm btn-outline-secondary me-1";
    editSettings.textContent = "Edit settings";
    editSettings.onclick = () => openTrainingSettings(editSettings, model);
    actions.append(editSettings);
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

async function openModelAnalysis(model) {
    const requestId = ++analysisRequest;
    const body = document.getElementById("modelAnalysisBody");
    document.getElementById("modelAnalysisTitle").textContent = `Analysis: ${model.model_id}`;
    body.replaceChildren();
    body.textContent = "Analyzing saved training results…";
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modelAnalysisModal")).show();
    try {
        const report = await analyzeModel(model.model_id);
        if (requestId === analysisRequest) renderModelAnalysis(body, report);
    } catch (error) {
        if (requestId === analysisRequest) body.textContent = `Could not analyze this model: ${error.message}. Close and click Analyze to retry.`;
    }
}

function renderModelAnalysis(body, report) {
    body.replaceChildren();
    const paragraph = (text, className = "mb-2") => {
        const element = document.createElement("p");
        element.className = className;
        element.textContent = text;
        body.append(element);
    };
    paragraph(report.source === "ai" ? "AI analysis of saved training evidence" : `Local evidence analysis · ${report.source_note || 'AI unavailable'}`, "small text-muted");
    paragraph(report.evidence.target);
    const evidence = report.evidence;
    if (evidence.market) paragraph(`Market: ${evidence.market.symbol} ${evidence.market.timeframe} · Source: ${DATA_SOURCE_LABELS[evidence.market.data_source] || evidence.market.data_source || 'not recorded'} · Training dataset: ${evidence.data_period.start_time} to ${evidence.data_period.end_time}`, "small text-muted");
    paragraph(`Inputs: ${evidence.feature_set_id} · Validation observations: ${evidence.validation_observations ?? 'not recorded'} · Folds: ${evidence.fold_count} · UP decision threshold: ${evidence.probability_threshold ?? 'not recorded'}`, "small text-muted");
    paragraph(report.summary, "fw-semibold");
    for (const metric of report.metrics || []) {
        const range = evidence.fold_ranges?.[metric.key];
        const score = Number.isFinite(metric.value) ? (['precision', 'recall', 'down_precision', 'down_recall'].includes(metric.key) ? `${(metric.value * 100).toFixed(1)}%` : metric.value.toFixed(3)) : 'not available';
        paragraph(`${metric.name}: ${score}${range ? ` · Fold range: ${range.min.toFixed(3)}–${range.max.toFixed(3)} (${range.folds_with_score} folds)` : ''}`, "fw-semibold mt-3 mb-1");
        paragraph(metric.explanation, "small");
    }
    const bins = (evidence.calibration_bins || []).filter(bin => bin.count > 0 && Number.isFinite(bin.mean_probability) && Number.isFinite(bin.observed_rate));
    if (bins.length) {
        paragraph("Probability calibration: predicted likelihood versus actual event frequency (closer is better).", "fw-semibold mt-3");
        for (const bin of bins) paragraph(`Predicted ${(bin.mean_probability * 100).toFixed(1)}% · Actual ${(bin.observed_rate * 100).toFixed(1)}% · ${bin.count} observations`, "small mb-1");
    }
    if (Number.isFinite(evidence.training_positive_rate)) paragraph(`UP event frequency in final training split: ${(evidence.training_positive_rate * 100).toFixed(1)}%. This is context, not a validation baseline score.`, "small mt-3");
    if (evidence.top_features?.length) paragraph(`Top inputs: ${evidence.top_features.map(item => `${item.feature} (${item.importance ?? 'unknown'})`).join(', ')}`, "small mt-3");
    for (const [label, items] of [["Strengths", report.strengths], ["Limitations", [...new Set([...(report.limitations || []), ...(report.evidence_notes || [])])]], ["Suggested next steps", report.next_steps]]) {
        if (!items?.length) continue;
        paragraph(label, "fw-semibold mt-3 mb-1");
        const list = document.createElement("ul");
        for (const text of items) {
            const item = document.createElement("li");
            item.textContent = text;
            list.append(item);
        }
        body.append(list);
    }
    paragraph(report.history_saved ? "Saved in model history. Model status is unchanged." : "Analysis could not be saved in model history. Model status is unchanged.", "small text-muted mt-3");
}

function formatMarketContext(context) {
    return context?.symbol && context?.timeframe ? `${context.symbol} · ${context.timeframe} · ${DATA_SOURCE_LABELS[context.data_source] || 'Source not recorded'}` : "—";
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
        ["UP precision", metrics.precision],
        ["UP recall", metrics.recall],
        ["UP ROC AUC", metrics.roc_auc],
        ["UP Brier", metrics.brier_score],
        ["DOWN precision", metrics.downside?.precision],
        ["DOWN recall", metrics.downside?.recall],
        ["DOWN ROC AUC", metrics.downside?.roc_auc],
        ["DOWN Brier", metrics.downside?.brier_score],
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
    if (modelDataSourcePending) {if (status) setTrainingStatus(status, "info", "Wait for the data-source preference to finish loading or saving."); return;}
    if (trainingSettingsPending) {if (status) setTrainingStatus(status, "info", "Wait for training settings to finish loading or saving."); return;}
    const dialog = document.getElementById("trainCandidateModal");
    if (!bars || !horizon || !threshold || !status || !dialog) return;
    button.disabled = true;
    setTrainingStatus(status, "info", "Training paper-only candidate from completed candles…");
    try {
        const result = await trainCandidate(parameters);
        if (result.status === "duplicate") {
            setTrainingStatus(status, "warning", `⚠ Training skipped: ${result.message}${result.replaced_model_ids?.length ? ` Removed ${result.replaced_model_ids.length} older candidate(s).` : ''}${result.cleanup_warnings?.length ? ` ${result.cleanup_warnings.join(' ')}` : ''}`);
            if (result.replaced_model_ids?.length) await refreshModelOperations();
            return;
        }
        await refreshModelOperations();
        document.getElementById("modelOperationsStatus").textContent = `Candidate ${result.model_id} trained on ${result.training_rows} rows${result.replaced_model_ids?.length ? `; replaced ${result.replaced_model_ids.length} previous candidate(s)` : ''}; review before promotion.${result.cleanup_warnings?.length ? ` ${result.cleanup_warnings.join(' ')}` : ''}`;
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
