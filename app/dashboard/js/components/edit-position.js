import {
    updatePosition
} from "../api.js";

let editingId = null;

export function initializeEditPosition() {

    window.addEventListener(
        "position-edit",
        onEditPosition
    );

    document
        .getElementById("btnSavePosition")
        .addEventListener(
            "click",
            savePosition
        );

}

function onEditPosition(event) {

    editingId = event.detail.id;

    const modal = new bootstrap.Modal(
        document.getElementById("editPositionModal")
    );

    modal.show();

}

async function savePosition() {

    await updatePosition(
        editingId,
        {
            stop_loss: parseFloat(
                document.getElementById("editSL").value
            ),
            take_profit: parseFloat(
                document.getElementById("editTP").value
            )
        }
    );

    bootstrap.Modal
        .getInstance(
            document.getElementById("editPositionModal")
        )
        .hide();

    window.dispatchEvent(
        new Event("dashboard-refresh")
    );

}