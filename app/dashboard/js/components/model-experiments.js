import { getControlledExperimentPlan, runControlledExperiments, getModelReviewHistory } from "../api.js";

let selection = 0;
let pending = null;
const reports = new Map();
const recipeNames = {"current-recipe": "Current recipe", "feature-check": "Alternative features",
    "conservative-calibration": "Simpler trees", "capacity-check": "More capacity",
    "promising-settings": "Promising settings", "simpler-trees": "Simpler trees",
    "slower-learning": "Slower learning", "more-capacity": "More capacity"};

function element(tag, text, className = "") {
    const node = document.createElement(tag);
    node.textContent = text;
    node.className = className;
    return node;
}

export async function openModelExperiments(model, refresh = async () => {}) {
    const token = ++selection;
    const body = document.getElementById("modelExperimentsBody");
    document.getElementById("modelExperimentsTitle").textContent = `Experiments: ${model.model_id}`;
    body.replaceChildren(element("p", "Loading experiment recipes…"));
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modelExperimentsModal")).show();
    try {
        const [plan, history] = await Promise.all([
            getControlledExperimentPlan(model.model_id),
            getModelReviewHistory(model.model_id).catch(() => []),
        ]);
        if (token !== selection) return;
        const saved = history.filter(event => event.type === "controlled_experiment").at(-1)?.evidence;
        renderExperimentPlan(body, plan, async (button, resultTarget, status) => {
            if (pending) {
                status.textContent = "An experiment is already running. Wait for it to finish, then retry.";
                return;
            }
            button.disabled = true;
            status.textContent = "Fetching one dataset and training the recipes… This may take a minute.";
            pending = runControlledExperiments(model.model_id);
            try {
                const report = await pending;
                reports.set(model.model_id, report);
                if (token === selection) {
                    renderExperimentResults(resultTarget, report);
                    status.textContent = report.status === "completed" ? "Experiment completed." : "Experiment finished with failures. Review each recipe below.";
                }
                try { await refresh(); }
                catch { if (token === selection) status.textContent += " Refresh the model list to see new candidates."; }
            } catch (error) {
                if (token === selection) status.textContent = `Experiment failed: ${error.message}. You can retry.`;
            } finally {
                pending = null;
                button.disabled = false;
            }
        }, reports.get(model.model_id) || saved);
    } catch (error) {
        if (token === selection) body.replaceChildren(element("p", `Could not load experiments: ${error.message}. Close and click Experiments to retry.`, "text-danger"));
    }
}

export function renderExperimentPlan(body, plan, run, report = null) {
    body.replaceChildren();
    const settings = plan.parameters;
    body.append(element("p", `${settings.symbol} · ${settings.timeframe} · ${settings.data_source} · up to ${settings.bars} candles. Reserve the latest ${plan.holdout_fraction * 100}% of shared labeled observations for evaluation.`, "small"));
    for (const note of plan.notes) body.append(element("p", note, "small text-muted"));
    const list = element("ul", "");
    for (const variant of plan.variants) {
        const p = variant.parameters;
        list.append(element("li", `${recipeNames[variant.id] || variant.id}: ${p.feature_set_id}, ${p.n_estimators} trees, depth ${p.max_depth}, learning rate ${p.learning_rate}. ${variant.rationale}`));
    }
    body.append(list);
    body.append(element("p", `Positive predictions use the same ${(settings.probability_threshold * 100).toFixed(0)}% threshold for every recipe.`, "small"));
    body.append(element("p", "This creates separate candidates and saves the results in this model’s History. The target and probability threshold stay the same for every recipe.", "small"));
    const button = element("button", `Run ${plan.variants.length} experiments`, "btn btn-primary");
    button.type = "button";
    const status = element("p", "", "small mt-2");
    status.setAttribute("aria-live", "polite");
    const results = element("div", "");
    button.onclick = () => run(button, results, status);
    body.append(button, status, results);
    if (report) renderExperimentResults(results, report);
}

export function renderExperimentResults(target, report) {
    target.replaceChildren();
    target.append(element("h6", "Results on the same unseen candles", "mt-4"));
    target.append(element("p", `${report.samples} observations · ${report.evaluation_start} to ${report.evaluation_end}. Training: ${report.training_rows} rows through ${report.training_end}; ${report.purge_candles}-candle purge before evaluation.`, "small"));
    target.append(element("p", "Brier score and log loss: lower is better. ROC AUC: higher is better. Brier skill: positive beats the baseline, negative is worse; zero is a tie.", "small"));
    const format = value => Number.isFinite(value) ? value.toFixed(4) : "Unavailable";
    for (const direction of ["up", "down"]) {
        const baseline = report.baseline[direction];
        target.append(element("h6", `${direction.toUpperCase()} · Historical-rate baseline ${(baseline.probability * 100).toFixed(1)}%; observed event rate ${(baseline.observed_rate * 100).toFixed(1)}%`, "mt-3"));
        const wrapper = element("div", "", "table-responsive");
        const table = element("table", "", "table table-sm align-middle");
        const head = element("thead", ""), header = element("tr", "");
        for (const label of ["Recipe / model", "Inputs", "ROC AUC", "Brier", "Log loss", "Brier skill", "Precision", "Recall", "Positive predictions", "Baseline check"]) header.append(element("th", label));
        head.append(header);
        const rows = element("tbody", "");
        const appendScores = (name, inputs, scores, id = "") => {
            const row = element("tr", "");
            const label = element("td", name);
            if (id) label.append(element("div", id, "small text-muted"));
            row.append(label, element("td", inputs));
            for (const key of ["roc_auc", "brier_score", "log_loss", "brier_skill", "precision", "recall"]) {
                const cell = element("td", format(scores[key]));
                if (key === "brier_skill" && Number.isFinite(scores[key])) cell.className = scores[key] > 0 ? "text-success" : scores[key] < 0 ? "text-danger" : "";
                row.append(cell);
            }
            row.append(element("td", String(scores.positive_predictions ?? "Unavailable")),
                element("td", scores.beats_baseline === true ? "Better Brier and log loss" : scores.beats_baseline === false ? "Needs improvement" : "Reference"));
            rows.append(row);
        };
        appendScores("Historical-rate baseline", "Constant probability", {...baseline.scores, brier_skill: 0});
        for (const result of report.results) {
            if (result.status !== "completed") continue;
            appendScores(recipeNames[result.recipe] || result.recipe, result.parameters.feature_set_id, result.scores[direction], result.model_id);
        }
        table.append(head, rows); wrapper.append(table); target.append(wrapper);
    }
    for (const result of report.results.filter(item => item.status !== "completed")) target.append(element("p", `${recipeNames[result.recipe] || result.recipe} failed: ${result.error}`, "text-danger small"));
    for (const note of report.notes || []) target.append(element("p", note, "small text-muted"));
    target.append(element("p", report.history_saved ? "Saved in this model’s History." : "History could not be saved. Keep these results before closing.", "small"));
}
