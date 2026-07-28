import {
    deleteStrategy
} from "./strategy-api.js";

import {
    openStrategyEditor
}
from "./strategy-editor.js";

export function renderStrategies(strategies) {

    const tbody =
        document.getElementById(
            "strategyTable"
        );

    tbody.innerHTML = "";

    for (const strategy of strategies) {

        tbody.insertAdjacentHTML(
            "beforeend",
            `
            <tr>

                <td>
                    ${strategy.name}
                </td>

                <td>
                    ${strategy.strategy_type}
                </td>

                <td>
                    ${strategy.description}
                </td>

                <td>

                    <button
                        class="btn btn-sm btn-primary editStrategy"
                        data-id="${strategy.id}">

                        Edit

                    </button>

                    <button
                        class="btn btn-sm btn-danger deleteStrategy"
                        data-id="${strategy.id}">

                        Delete

                    </button>

                </td>

            </tr>
            `
        );

    }

    wireButtons();

}

function wireButtons() {

    document
        .querySelectorAll(".deleteStrategy")
        .forEach(button => {

            button.onclick =
                async () => {

                    if (!confirm(
                        "Delete this strategy?"
                    )) {

                        return;

                    }

                    await deleteStrategy(
                        button.dataset.id
                    );

                    location.reload();

                };

        });

    document
        .querySelectorAll(".editStrategy")
        .forEach(button => {

            button.onclick =
                () => {

                    openStrategyEditor(
                        button.dataset.id
                    );

                };

        });

}