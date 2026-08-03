import {
    getStrategies
}
from "./strategy-api.js";

import {
    renderStrategies
}
from "./strategy-renderer.js";

import {
    openStrategyEditor
}
from "./strategy-editor.js";

async function load() {

    const strategies =
        await getStrategies();

    renderStrategies(
        strategies
    );

}

document
    .getElementById(
        "btnNewStrategy"
    )
    .onclick = () => {

        openStrategyEditor();

    };

load();