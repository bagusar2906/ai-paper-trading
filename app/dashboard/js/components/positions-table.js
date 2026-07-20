import {
    closePosition,
} from "../api.js";

export function updatePositions(positions) {

    const tbody =
        document.querySelector("#positionsTable tbody");

    if (!tbody)
        return;

    tbody.replaceChildren();

    positions.forEach(position => {

        tbody.appendChild(
            createRow(position)
        );

    });

    document.getElementById("positionCount").textContent =
        positions.length;

}

function createRow(position) {

    const tr = document.createElement("tr");

    tr.innerHTML = `
        <td>${position.symbol}</td>

        <td>
            <span class="badge ${
                position.side === "BUY"
                    ? "bg-success"
                    : "bg-danger"
            }">
                ${position.side}
            </span>
        </td>

        <td>${position.entry_price.toFixed(2)}</td>

        <td>${position.stop_loss.toFixed(2)}</td>

        <td>${position.take_profit.toFixed(2)}</td>

        <td>${formatProfit(position.floating_pnl)}</td>

        <td>${position.current_price?.toFixed(2) ?? "-"}</td>

        <td></td>
    `;

    tr.lastElementChild.appendChild(
        createActions(position)
    );

    return tr;

}

function createActions(position) {

    const container =
        document.createElement("div");

    container.className = "btn-group btn-group-sm";

    container.appendChild(
        createEditButton(position)
    );

    container.appendChild(
        createCloseButton(position)
    );

    return container;

}

function createEditButton(position) {

    const button =
        document.createElement("button");

    button.className =
        "btn btn-outline-primary";

    button.innerHTML = "✏";

    button.title = "Modify";

    button.onclick = () => {

        window.dispatchEvent(
            new CustomEvent(
                "position-edit",
                {
                    detail: position
                }
            )
        );

    };

    return button;

}

function createCloseButton(position) {

    const button =
        document.createElement("button");

    button.className =
        "btn btn-outline-danger";

    button.innerHTML = "✖";

    button.title = "Close";

    button.onclick = async () => {

        if (
            !confirm(
                `Close ${position.side} ${position.symbol}?`
            )
        ) {
            return;
        }

        try {

            await closePosition(position.id);

            window.dispatchEvent(
                new Event("dashboard-refresh")
            );

        }
        catch (error) {

            console.error(error);

            alert("Unable to close position.");

        }

    };

    return button;

}

function formatProfit(value) {

    if (value == null)
        return "-";

    const color =
        value >= 0
            ? "green"
            : "red";

    return `<span style="color:${color}">
        ${value.toFixed(2)}
    </span>`;

}