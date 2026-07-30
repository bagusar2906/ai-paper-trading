import {
    getStrategy,
    createStrategy,
    updateStrategy
}
    from "./strategy-api.js";

let modal;

let editingId = null;

export async function openStrategyEditor(id = null) {

    if (!modal) {

        modal =
            new bootstrap.Modal(
                document.getElementById(
                    "strategyModal"
                )
            );

    }

    editingId = id;

    if (id == null) {

        clearForm();

        renderParameterEditor();

    }
    else {

        const strategy =
            await getStrategy(id);

        fillForm(strategy);

    }

    modal.show();

}

function renderParameterEditor() {

    const div =
        document.getElementById(
            "strategyParameters"
        );

    div.innerHTML = `

        <div class="row">

            <div class="col">

                <label>EMA Length</label>

                <input
                    id="emaLength"
                    class="form-control"
                    type="number"
                    value="200">

            </div>

            <div class="col">

                <label>RSI Length</label>

                <input
                    id="rsiLength"
                    class="form-control"
                    type="number"
                    value="14">

            </div>

            <div class="col">

                <label>ADX Length</label>

                <input
                    id="adxLength"
                    class="form-control"
                    type="number"
                    value="14">

            </div>

        </div>

        <div class="row mt-3">

            <div class="col">

                <label>ADX Level</label>

                <input
                    id="adxLevel"
                    class="form-control"
                    type="number"
                    value="25">

            </div>

            <div class="col">

                <label>Oversold</label>

                <input
                    id="rsiOS"
                    class="form-control"
                    type="number"
                    value="20">

            </div>

            <div class="col">

                <label>Overbought</label>

                <input
                    id="rsiOB"
                    class="form-control"
                    type="number"
                    value="80">

            </div>

        </div>

    `;

}

function clearForm() {

    document.getElementById(
        "strategyName"
    ).value = "";

    document.getElementById(
        "strategyDescription"
    ).value = "";

}

function fillForm(strategy) {

    document.getElementById(
        "strategyName"
    ).value = strategy.name;

    document.getElementById(
        "strategyDescription"
    ).value = strategy.description;

    document.getElementById(
        "strategyType"
    ).value = strategy.strategy_type;

    renderParameterEditor();

    const config =
        JSON.parse(strategy.config_json);

    document.getElementById("emaLength").value =
        config.ema_length;

    document.getElementById("rsiLength").value =
        config.rsi_length;

    document.getElementById("adxLength").value =
        config.adx_length;

    document.getElementById("adxLevel").value =
        config.adx_level;

    document.getElementById("rsiOS").value =
        config.oversold;

    document.getElementById("rsiOB").value =
        config.overbought;
}

document
    .getElementById("btnSaveStrategy")
    .onclick = saveStrategy;

async function saveStrategy() {


    console.log("Saving strategy...");

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

        config_json: JSON.stringify({

            ema_length:
                parseInt(document.getElementById("emaLength").value),

            rsi_length:
                parseInt(document.getElementById("rsiLength").value),

            adx_length:
                parseInt(document.getElementById("adxLength").value),

            adx_level:
                parseInt(document.getElementById("adxLevel").value),

            oversold:
                parseInt(document.getElementById("rsiOS").value),

            overbought:
                parseInt(document.getElementById("rsiOB").value)

        })
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

