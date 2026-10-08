import {
    getStrategy,
    createStrategy,
    updateStrategy,
    getStrategyTypes,
    getStrategySchema
}
from "./strategy-api.js";

let modal;
let editingId = null;
let currentSchema = [];

export async function openStrategyEditor(id = null) {

    if (!modal) {

        modal = new bootstrap.Modal(
            document.getElementById("strategyModal")
        );

    }

    editingId = id;

    document.getElementById(
        "strategyModalTitle"
    ).innerText = id == null ? "New Strategy" : "Edit Strategy";

    // Show the dialog before awaiting API calls. This gives the user immediate
    // feedback and avoids a click that appears to do nothing on a failed call.
    modal.show();

    try {

        await loadStrategyTypes();

        if (id == null) {

            clearForm();

            const schema =
                await getStrategySchema(

                    document.getElementById(
                        "strategyType"
                    ).value

                );

            renderParameterEditor(schema);

        }
        else {

            const strategy =
                await getStrategy(id);

            await fillForm(strategy);

        }

    }
    catch (error) {

        modal.hide();
        throw error;

    }

}


async function loadStrategyTypes() {

    const select =
        document.getElementById(
            "strategyType"
        );

    const strategies =
        await getStrategyTypes();

    select.innerHTML = "";

    strategies.forEach(strategy => {

        select.innerHTML += `

            <option value="${strategy.value}">
                ${strategy.label}
            </option>

        `;

    });

}


function renderParameterEditor(schema) {

    currentSchema = schema;

    const div =
        document.getElementById(
            "strategyParameters"
        );

    div.innerHTML = "";

    schema.forEach(field => {

        if (field.type === "select") {
            div.innerHTML += `<div class="mb-3"><label class="form-label" for="${field.key}">${field.label}</label>
                <select id="${field.key}" class="form-select">${(field.options || []).map(option => `<option value="${option.value}" ${option.value === field.default ? "selected" : ""}>${option.label}</option>`).join("")}</select>
                ${field.description ? `<div class="form-text">${field.description}</div>` : ""}</div>`;
            return;
        }

        if (field.type === "boolean") {
            div.innerHTML += `<div class="form-check mb-3">
                <input id="${field.key}" class="form-check-input" type="checkbox" ${field.default === true ? "checked" : ""}>
                <label class="form-check-label" for="${field.key}">${field.label}</label>
                ${field.description ? `<div class="form-text">${field.description}</div>` : ""}
            </div>`;
            return;
        }

        div.innerHTML += `

            <div class="mb-3">

                <label class="form-label">
                    ${field.label}
                </label>

                <input
                    id="${field.key}"
                    class="form-control"
                    type="${field.type}"
                    value="${field.default}"
                    min="${field.minimum ?? ""}"
                    max="${field.maximum ?? ""}"
                    step="${field.step ?? ""}">
                ${field.description ? `<div class="form-text">${field.description}</div>` : ""}

            </div>

        `;

    });

    const technicalToggle = document.getElementById("use_technical_filters");
    if (technicalToggle) technicalToggle.addEventListener("change", updateModelEntryFields);
    document.getElementById("feature_set_id")?.addEventListener("change", updateModelEntryFields);
    updateModelEntryFields();

}

function updateModelEntryFields() {
    const toggle = document.getElementById("use_technical_filters");
    if (!toggle) return;
    const rawInputs = document.getElementById("feature_set_id")?.value === "raw-ohlcv-v1";
    if (rawInputs) toggle.checked = false;
    toggle.disabled = rawInputs;
    for (const key of ["adx_threshold", "stop_atr_multiple"]) {
        const input = document.getElementById(key);
        if (input) input.disabled = !toggle.checked;
    }
    const fixedStop = document.getElementById("model_stop_loss_percent");
    if (fixedStop) fixedStop.disabled = toggle.checked;
}


function clearForm() {

    document.getElementById(
        "strategyName"
    ).value = "";

    document.getElementById(
        "strategyDescription"
    ).value = "";

}


async function fillForm(strategy) {

    document.getElementById(
        "strategyName"
    ).value = strategy.name;

    document.getElementById(
        "strategyDescription"
    ).value = strategy.description;

    document.getElementById(
        "strategyType"
    ).value = strategy.strategy_type;

    const schema =
        await getStrategySchema(
            strategy.strategy_type
        );

    renderParameterEditor(schema);

    const config = typeof strategy.config === "string"
        ? JSON.parse(strategy.config)
        : (strategy.config || {});

    schema.forEach(field => {

        const input =
            document.getElementById(
                field.key
            );

        if (input && field.key === "down_probability_threshold" &&
            config.down_probability_threshold === undefined &&
            Number.isFinite(config.short_probability_threshold)) {
            input.value = 1 - config.short_probability_threshold;
            return;
        }

        if (
            input &&
            config[field.key] !== undefined
        ) {

            if (field.type === "boolean") {
                input.checked = config[field.key] === true;
            } else {
                input.value = config[field.key];
            }

        }

    });

    updateModelEntryFields();

}


document
    .getElementById("strategyType")
    .addEventListener(
        "change",
        async () => {

            const schema =
                await getStrategySchema(

                    document.getElementById(
                        "strategyType"
                    ).value

                );

            renderParameterEditor(schema);

        }
    );


document
    .getElementById("btnSaveStrategy")
    .onclick = saveStrategy;


async function saveStrategy() {

    console.log("Saving strategy...");

    const config = {};

    currentSchema.forEach(field => {

        const input =
            document.getElementById(
                field.key
            );

        if (!input)
            return;

        let value = input.value;

        if (field.type === "boolean") value = input.checked;

        if (field.type === "number") {

            value = Number(value);

        }

        config[field.key] = value;

    });

    const request = {

        name:
            document.getElementById(
                "strategyName"
            ).value,

        description:
            document.getElementById(
                "strategyDescription"
            ).value,

        strategy_type:
            document.getElementById(
                "strategyType"
            ).value,

        config: JSON.stringify(config)

    };

    if (editingId == null) {

        await createStrategy(request);

    }
    else {

        await updateStrategy(
            editingId,
            request
        );

    }

    modal.hide();

    location.reload();

}
