import { getModels, promoteModel, rollbackModel } from "../api.js";

export async function refreshModelOperations() {
    const body = document.querySelector("#modelOperations tbody");
    const status = document.getElementById("modelOperationsStatus");
    if (!body) return;
    try {
        const models = await getModels();
        body.replaceChildren(...models.map(model => row(model)));
        status.textContent = models.some(model => model.status === "champion") ? "Paper-only champion available" : "No champion — AI strategy will hold";
    } catch (error) {
        status.textContent = `Model status unavailable: ${error.message}`;
    }
}

function row(model) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${model.model_id}</td><td><span class="badge text-bg-${model.status === "champion" ? "success" : "secondary"}">${model.status}</span></td><td>${model.feature_set_id}</td><td></td>`;
    const actions = tr.lastElementChild;
    if (model.status === "candidate" || model.status === "retired") {
        const button = document.createElement("button");
        button.className = "btn btn-sm btn-outline-primary";
        button.textContent = model.status === "candidate" ? "Promote" : "Rollback";
        button.onclick = () => operate(model, button);
        actions.append(button);
    }
    return tr;
}

async function operate(model, button) {
    const reviewer = window.prompt("Reviewer name (required):");
    const rationale = window.prompt("Rationale (required):");
    if (!reviewer || !rationale) return;
    button.disabled = true;
    try {
        if (model.status === "candidate") await promoteModel(model.model_id, reviewer, rationale);
        else await rollbackModel(model.model_id, reviewer, rationale);
        await refreshModelOperations();
    } catch (error) {
        window.alert(`Model operation failed: ${error.message}`);
        button.disabled = false;
    }
}
