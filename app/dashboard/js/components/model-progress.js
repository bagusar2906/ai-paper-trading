import { getModelTrainingProgress } from "../api.js";

let progressRequest = 0;
const METRICS = {
    roc_auc: ["ROC AUC", "Higher is better"],
    brier_score: ["Brier score", "Lower is better"],
    precision: ["Precision", "Higher means fewer incorrect positive predictions"],
    recall: ["Recall", "Higher means more actual events detected"],
    log_loss: ["Log loss", "Lower is better"],
};

export async function openModelProgress(model) {
    const requestId = ++progressRequest;
    const body = document.getElementById("modelProgressBody");
    document.getElementById("modelProgressTitle").textContent = `Training progress: ${model.model_id}`;
    body.replaceChildren();
    body.textContent = "Loading recorded training results…";
    bootstrap.Modal.getOrCreateInstance(document.getElementById("modelProgressModal")).show();
    try {
        const report = await getModelTrainingProgress(model.model_id);
        if (requestId === progressRequest) renderModelProgress(body, report);
    } catch (error) {
        if (requestId === progressRequest) body.textContent = `Could not load progress: ${error.message}. Close and click Progress to retry.`;
    }
}

function element(tag, text, className = "") {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    node.className = className;
    return node;
}

function dateLabel(value) {
    if (!value) return "Not recorded";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Not recorded" : date.toLocaleString();
}

function score(value) {
    return Number.isFinite(value) ? value.toFixed(3) : "—";
}

export function renderModelProgress(body, report) {
    body.replaceChildren();
    body.append(element("p", `${report.runs.length} completed run(s) with the same recorded setup. The selected model is highlighted.`, "mb-2"));
    if (report.runs.length < 2) body.append(element("p", "Only one matching run is recorded, so a trend across retraining runs is not yet available. You can view this model’s validation periods instead.", "alert alert-info"));
    if (!report.matching_history_available) body.append(element("p", "Older metadata does not identify a comparable training family. Showing only the selected model.", "small text-muted"));
    if (report.limited) body.append(element("p", "Showing up to the 200 most recent matching runs, including the selected model.", "small text-muted"));
    const controls = element("div", undefined, "d-flex flex-wrap gap-3 mb-3");
    const view = element("select", undefined, "form-select form-select-sm");
    view.id = "modelProgressView";
    for (const [value, text] of [["runs", "Completed training runs"], ["folds", "Selected model’s validation periods"]]) {
        const option = element("option", text); option.value = value; view.append(option);
    }
    view.value = "runs";
    const metric = element("select", undefined, "form-select form-select-sm");
    metric.id = "modelProgressMetric";
    for (const [value, [text]] of Object.entries(METRICS)) {
        const option = element("option", text); option.value = value; metric.append(option);
    }
    metric.value = "roc_auc";
    for (const [label, select] of [["View", view], ["Metric", metric]]) {
        const group = element("div"); const caption = element("label", label, "form-label");
        caption.htmlFor = select.id; group.append(caption, select); controls.append(group);
    }
    body.append(controls);
    const output = element("div"); body.append(output);
    const draw = () => {
        output.replaceChildren();
        const points = view.value === "folds" ? report.folds : report.runs;
        const [name, direction] = METRICS[metric.value];
        output.append(element("p", `${name}: ${direction}. Blue solid = UP; orange dashed = DOWN.`, "small mb-2"));
        renderProgressChart(output, points, metric.value, view.value);
        renderProgressTable(output, points, metric.value, view.value);
    };
    view.onchange = metric.onchange = draw;
    draw();
    for (const note of report.notes || []) body.append(element("p", note, "small text-muted mt-2 mb-1"));
}

function svgElement(tag, attributes, text) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = text;
    return node;
}

function renderProgressChart(container, points, metric, view) {
    const values = points.flatMap(point => [point.metrics?.up?.[metric], point.metrics?.down?.[metric]]).filter(Number.isFinite);
    if (!values.length) {
        container.append(element("p", "No valid scores are recorded for this metric and view. Choose another metric or train a new candidate.", "alert alert-info"));
        return;
    }
    const svg = svgElement("svg", {viewBox: "0 0 820 320", width: "100%", role: "img", "aria-label": `${METRICS[metric][0]} across ${view === "runs" ? "completed training runs" : "validation periods"}`});
    svg.style.maxHeight = "360px";
    const top = metric === "log_loss" ? Math.max(1, ...values) * 1.1 : 1;
    const x = index => points.length > 1 ? 60 + index * 720 / (points.length - 1) : 420;
    const y = value => 265 - value * 235 / top;
    for (let tick = 0; tick <= 4; tick++) {
        const value = top * tick / 4;
        svg.append(svgElement("line", {x1: 60, x2: 780, y1: y(value), y2: y(value), stroke: "#dee2e6"}));
        svg.append(svgElement("text", {x: 50, y: y(value) + 4, "text-anchor": "end", "font-size": 12, fill: "#495057"}, value.toFixed(2)));
    }
    const selected = points.findIndex(point => point.selected);
    if (selected >= 0) svg.append(svgElement("line", {x1: x(selected), x2: x(selected), y1: 20, y2: 265, stroke: "#495057", "stroke-dasharray": "3 4"}));
    for (const [side, color, dash] of [["up", "#0d6efd", ""], ["down", "#a95300", "6 4"]]) {
        let previous = null;
        points.forEach((point, index) => {
            const value = point.metrics?.[side]?.[metric];
            if (!Number.isFinite(value)) { previous = null; return; }
            if (previous) svg.append(svgElement("line", {x1: previous.x, y1: previous.y, x2: x(index), y2: y(value), stroke: color, "stroke-width": 2, "stroke-dasharray": dash}));
            const label = view === "folds" ? point.label : `Run ${index + 1}`;
            const description = `${label}${point.selected ? " (selected model)" : ""} · ${side.toUpperCase()} ${METRICS[metric][0]}: ${score(value)} · ${view === "folds" ? `${dateLabel(point.validation_start)} to ${dateLabel(point.validation_end)}` : `${dateLabel(point.created_at)} · ${point.model_id || point.training_run_id}`}`;
            const circle = svgElement("circle", {cx: x(index), cy: y(value), r: point.selected ? 6 : 4, fill: color, stroke: "white", "stroke-width": 1, tabindex: 0, "aria-label": description});
            circle.append(svgElement("title", {}, description)); svg.append(circle);
            previous = {x: x(index), y: y(value)};
        });
    }
    const labels = new Set(Array.from({length: Math.min(6, points.length)}, (_, i) => Math.round(i * (points.length - 1) / Math.max(1, Math.min(6, points.length) - 1))));
    for (const index of labels) svg.append(svgElement("text", {x: x(index), y: 290, "text-anchor": "middle", "font-size": 12, fill: "#495057"}, view === "folds" ? points[index].label : `Run ${index + 1}${points[index].selected ? " *" : ""}`));
    container.append(svg);
    container.append(element("p", "Hover or focus a point for its date and exact score. Missing scores create gaps. DOWN scores are unavailable for older UP-only records.", "small text-muted"));
}

function renderProgressTable(container, points, metric, view) {
    const details = element("details"); details.append(element("summary", "Dates and exact scores"));
    const wrapper = element("div", undefined, "table-responsive");
    const table = element("table", undefined, "table table-sm mt-2");
    const head = element("thead"), header = element("tr"), body = element("tbody");
    const columns = view === "folds" ? ["Period", "Validation dates", "UP", "DOWN"] : ["Run", "Completed", "Model", "UP", "DOWN"];
    for (const label of columns) header.append(element("th", label)); head.append(header); table.append(head, body);
    points.forEach((point, index) => {
        const row = element("tr", undefined, point.selected ? "table-primary" : "");
        const cells = view === "folds" ? [point.label, `${dateLabel(point.validation_start)} to ${dateLabel(point.validation_end)}`] : [`Run ${index + 1}${point.selected ? " (selected)" : ""}`, dateLabel(point.created_at), point.model_id || point.training_run_id];
        cells.push(score(point.metrics?.up?.[metric]), score(point.metrics?.down?.[metric]));
        for (const value of cells) row.append(element("td", value)); body.append(row);
    });
    wrapper.append(table); details.append(wrapper); container.append(details);
}
