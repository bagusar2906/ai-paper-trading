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

    await loadStrategyTypes();

    if (id == null) {

        document.getElementById(
            "strategyModalTitle"
        ).innerText = "New Strategy";

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

        document.getElementById(
            "strategyModalTitle"
        ).innerText = "Edit Strategy";

        const strategy =
            await getStrategy(id);

        await fillForm(strategy);

    }

    modal.show();

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

            </div>

        `;

    });

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

    const config = strategy.config;

    schema.forEach(field => {

        const input =
            document.getElementById(
                field.key
            );

        if (
            input &&
            config[field.key] !== undefined
        ) {

            input.value =
                config[field.key];

        }

    });

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