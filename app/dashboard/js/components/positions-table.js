import {
    closePosition
} from "../api.js";

export function updatePositions(positions, tradingMode = "-") {

    const tbody =
        document.querySelector("#positionsTable tbody");

    if (!tbody)
        return;

    tbody.innerHTML = "";

    positions.forEach(position => {

        const pnlClass =
            position.floating_pnl >= 0
                ? "text-success"
                : "text-danger";

        tbody.innerHTML += `
        <tr>

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

            <td>${formatEntryTime(position.opened_at)}</td>

            <td>
                <span class="badge ${tradingMode === "AUTO" ? "bg-primary" : "bg-secondary"}">
                    ${tradingMode}
                </span>
            </td>

            <td>${position.current_price?.toFixed(2) ?? "-"}</td>

            <td class="${pnlClass}">
                ${(position.floating_pnl ?? 0).toFixed(2)}
            </td>

            <td>${position.stop_loss.toFixed(2)}</td>

            <td>${position.take_profit.toFixed(2)}</td>

            <td>

                <button
                    class="btn btn-sm btn-outline-primary edit-position"
                    data-id="${position.id}">

                    Edit

                </button>

                <button
                    class="btn btn-sm btn-outline-danger close-position"
                    data-id="${position.id}">

                    Close

                </button>

            </td>

        </tr>
        `;

    });

    attachEvents();

    document.getElementById("positionCount").textContent =
        positions.length;

}

function formatEntryTime(value) {

    if (!value) return "-";

    const entryTime = new Date(value);

    return Number.isNaN(entryTime.getTime())
        ? "-"
        : entryTime.toLocaleString();
}

function attachEvents() {

    document
        .querySelectorAll(".close-position")
        .forEach(button => {

            button.onclick = async () => {

                if (!confirm("Close this position?"))
                    return;

                await closePosition(
                    button.dataset.id
                );

                window.dispatchEvent(
                    new Event("dashboard-refresh")
                );

            };

        });

    document
        .querySelectorAll(".edit-position")
        .forEach(button => {

            button.onclick = () => {

                openEditModal(
                    button.dataset.id
                );

            };

        });

}

function openEditModal(id) {

    window.dispatchEvent(
        new CustomEvent(
            "position-edit",
            {
                detail: {
                    id
                }
            }
        )
    );

}
