import {
    activateStrategy,
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
                    ${strategy.is_active ? '<span class="badge text-bg-success ms-1">Active</span>' : ''}
                </td>

                <td>
                    ${strategy.strategy_type}
                </td>

                <td>
                    ${strategy.description}
                </td>

                <td class="strategy-actions-cell">

                    <div class="d-flex flex-nowrap gap-1 align-items-center">

                    <button
                        type="button"
                        class="btn btn-sm btn-success activateStrategy"
                        data-id="${strategy.id}"
                        ${strategy.is_active ? "disabled" : ""}>

                        ${strategy.is_active ? "Active" : "Activate"}

                    </button>

                    <button
                        type="button"
                        class="btn btn-sm btn-primary editStrategy"
                        data-id="${strategy.id}">

                        Edit

                    </button>

                    <button
                        type="button"
                        class="btn btn-sm btn-danger deleteStrategy"
                        data-id="${strategy.id}">

                        Delete

                    </button>

                    </div>

                </td>

            </tr>
            `
        );

    }

    wireButtons();

}

function wireButtons() {

    document
        .querySelectorAll(".activateStrategy")
        .forEach(button => {

            button.onclick = async () => {

                await activateStrategy(button.dataset.id);

                location.reload();

            };

        });

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

            button.onclick = async () => {

                try {
                    await openStrategyEditor(button.dataset.id);
                }
                catch (error) {
                    console.error("Could not open strategy editor", error);
                    alert(`Could not open strategy editor: ${error.message}`);
                }

            };

        });

}
