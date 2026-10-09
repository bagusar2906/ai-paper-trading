import { reviewTrainingCoach, runTrainingCoach, validateTrainingCoach } from "../api.js";
import { renderExperimentResults } from "./model-experiments.js";

let requestId = 0;
let busy = false;
const recipeName = id => ({"current-recipe": "Current recipe", "feature-check": "Alternative features",
    "conservative-calibration": "Simpler trees", "capacity-check": "More capacity",
    "promising-settings": "Promising settings", "simpler-trees": "Simpler trees",
    "slower-learning": "Slower learning", "more-capacity": "More capacity"}[id] || id);

function node(tag, text = "", className = "") {
    const result = document.createElement(tag);
    result.textContent = text;
    result.className = className;
    return result;
}

export async function openTrainingCoach(model, refresh = async () => {}) {
    const token = ++requestId;
    const body = document.getElementById("trainingCoachBody");
    document.getElementById("trainingCoachTitle").textContent = `Training coach: ${model.model_id}`;
    body.replaceChildren(node("p", "Reviewing saved experiment evidence..."));
    bootstrap.Modal.getOrCreateInstance(document.getElementById("trainingCoachModal")).show();
    try {
        const report = await reviewTrainingCoach(model.model_id);
        if (token !== requestId) return;
        show(report);
    } catch (error) {
        if (token === requestId) body.replaceChildren(node("p", `Coach unavailable: ${error.message}. Close and click Coach to retry.`, "text-danger"));
    }
    function show(report) {
        const actions = {
            review: () => reviewTrainingCoach(model.model_id),
            run: () => runTrainingCoach(model.model_id, report.coach_id),
            validate: () => validateTrainingCoach(model.model_id),
        };
        renderTrainingCoach(body, report, async (action, buttons, status, results) => {
            if (busy) {
                status.textContent = "A coach action is already running. Wait for it to finish.";
                return;
            }
            busy = true;
            for (const button of buttons) button.disabled = true;
            status.textContent = action === "run" ? "Running the recommended recipes on a new shared period..." :
                action === "validate" ? "Checking saved models against new candles with known outcomes..." : "Reviewing updated evidence...";
            try {
                const outcome = await actions[action]();
                if (token !== requestId) return;
                if (action === "review") {
                    show(outcome);
                    return;
                }
                if (outcome.status === "waiting_for_fresh_data") {
                    results.replaceChildren();
                    renderFreshValidation(results, outcome);
                    status.textContent = "Waiting for fresh data. Retry when more candles have completed.";
                } else {
                    if (action === "run") renderExperimentResults(results, outcome);
                    else renderFreshValidation(results, outcome);
                    status.textContent = "Finished. Use Review results to update the coach's diagnosis and tracking.";
                    if (action === "run") {
                        try { await refresh(); }
                        catch { status.textContent += " Refresh the model list to see the new candidates."; }
                    }
                }
            } catch (error) {
                if (token === requestId) status.textContent = `Coach action failed: ${error.message}. You can retry.`;
            } finally {
                busy = false;
                for (const button of buttons) button.disabled = button.dataset.action === "validate" && !report.can_validate || button.dataset.action === "run" && !report.history_saved;
            }
        });
    }
}

export function renderTrainingCoach(body, report, action) {
    body.replaceChildren();
    body.append(node("p", report.source === "ai" ? "AI training coach" : "Local evidence coach", "small text-muted"));
    if (report.source_note) body.append(node("p", report.source_note, "small text-muted"));
    body.append(node("p", report.summary, "fw-semibold"));
    const context = report.evidence.market_context;
    body.append(node("p", `${context.symbol} / ${context.timeframe} / ${context.data_source}. Target: ${report.evidence.label_definition_id}. Decision threshold: ${(report.evidence.probability_threshold * 100).toFixed(0)}%.`, "small"));
    for (const [title, items] of [["Observed evidence", report.findings], ["Coach reasoning", report.reasoning], ["Limits of the evidence", report.caveats]]) {
        body.append(node("h6", title, "mt-3"));
        const list = node("ul");
        for (const item of items || []) list.append(node("li", item));
        body.append(list);
    }
    body.append(node("h6", "Recommended next tests", "mt-3"));
    const recipes = node("ul");
    for (const variant of report.plan.variants) {
        const p = variant.parameters;
        recipes.append(node("li", `${recipeName(variant.id)}: ${p.feature_set_id}, ${p.n_estimators} trees, depth ${p.max_depth}, learning rate ${p.learning_rate}. ${variant.rationale}`));
    }
    body.append(recipes);
    if (report.plan.fresh_after) body.append(node("p", `New evaluation outcomes must start after ${report.plan.fresh_after}. At least 50 shared observations with known outcomes are required.`, "small"));
    body.append(node("h6", "Do earlier gains hold up?", "mt-3"));
    if (!report.tracking.length) {
        body.append(node("p", "Run a controlled experiment first to establish recipes for fresh validation.", "small"));
    } else {
        const wrapper = node("div", "", "table-responsive"), table = node("table", "", "table table-sm");
        const head = node("thead"), header = node("tr"), rows = node("tbody");
        for (const label of ["Recipe / model", "Initial baseline check", "Fresh periods", "Periods beating baseline", "Fresh evidence"]) header.append(node("th", label));
        head.append(header);
        const state = {not_yet_validated: "Awaiting fresh validation", held_up: "Baseline beaten in all tested fresh periods",
            mixed_or_worse: "Mixed or worse; investigate"};
        for (const item of report.tracking) {
            const row = node("tr"), label = node("td", recipeName(item.recipe));
            label.append(node("div", item.model_id, "small text-muted"));
            row.append(label, node("td", item.initial_beats_baseline ? "Better Brier and log loss in UP and DOWN" : "Needs improvement"),
                node("td", String(item.fresh_periods)), node("td", String(item.fresh_periods_beating_baseline)), node("td", state[item.status] || item.status));
            rows.append(row);
        }
        table.append(head, rows); wrapper.append(table); body.append(wrapper);
    }
    if (report.validation_history.length) {
        const details = node("details"), summary = node("summary", "Saved fresh validation periods");
        details.append(summary);
        for (const period of report.validation_history) {
            const section = node("div");
            renderFreshValidation(section, {...period, status: "completed", results: period.recipes, history_saved: true});
            details.append(section);
        }
        body.append(details);
    }
    body.append(node("p", report.history_saved ? "Coach review saved in model History." : "Coach review could not be saved. Review again before running recommendations.", "small text-muted"));
    const controls = node("div", "", "d-flex flex-wrap gap-2 mt-3");
    const buttons = [];
    for (const [key, label] of [["review", "Review results"], ["run", `Run ${report.plan.variants.length} recommended tests`], ["validate", "Validate on fresh data"]]) {
        const button = node("button", label, "btn btn-sm btn-outline-primary");
        button.type = "button";
        button.dataset.action = key;
        button.disabled = key === "validate" && !report.can_validate || key === "run" && !report.history_saved;
        buttons.push(button); controls.append(button);
    }
    const status = node("p", "", "small mt-2");
    status.setAttribute("aria-live", "polite");
    const results = node("div");
    for (const button of buttons) button.onclick = () => action(button.dataset.action, buttons, status, results);
    body.append(controls, status, results);
}

export function renderFreshValidation(target, report) {
    target.replaceChildren();
    if (report.status === "waiting_for_fresh_data") {
        target.append(node("p", `Waiting for fresh data: ${report.samples} of ${report.required_samples} required labeled observations after ${report.fresh_after}.`, "alert alert-info mt-3"));
        for (const note of report.notes || []) target.append(node("p", note, "small"));
        return;
    }
    target.append(node("h6", "Fresh validation of saved models", "mt-3"));
    target.append(node("p", `${report.samples} observations / ${report.evaluation_start} to ${report.evaluation_end}. Saved artifacts were evaluated without retraining.`, "small"));
    const wrapper = node("div", "", "table-responsive"), table = node("table", "", "table table-sm");
    const head = node("thead"), header = node("tr"), rows = node("tbody");
    for (const label of ["Recipe", "UP ROC AUC", "UP Brier skill", "DOWN ROC AUC", "DOWN Brier skill", "Baseline check"]) header.append(node("th", label));
    head.append(header);
    const format = value => Number.isFinite(value) ? value.toFixed(4) : "Unavailable";
    for (const result of report.results || []) {
        if (result.status !== "completed") {
            target.append(node("p", `${recipeName(result.recipe)}: ${result.error || "Result unavailable"}`, "text-danger small"));
            continue;
        }
        const up = result.scores.up, down = result.scores.down, row = node("tr");
        row.append(node("td", recipeName(result.recipe)), node("td", format(up.roc_auc)), node("td", format(up.brier_skill)),
            node("td", format(down.roc_auc)), node("td", format(down.brier_skill)),
            node("td", up.beats_baseline && down.beats_baseline ? "Both directions beat baseline" : "Needs improvement"));
        rows.append(row);
    }
    table.append(head, rows); wrapper.append(table); target.append(wrapper);
    for (const note of report.notes || []) target.append(node("p", note, "small text-muted"));
    target.append(node("p", report.history_saved ? "Fresh validation saved in model History." : "Fresh validation could not be saved.", "small text-muted"));
}
