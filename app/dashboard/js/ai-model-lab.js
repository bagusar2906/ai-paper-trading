import { initializeModelOperations, refreshModelOperations } from "./components/model-operations.js";

document.addEventListener("DOMContentLoaded", async () => {
    initializeModelOperations();
    await refreshModelOperations();
    setInterval(refreshModelOperations, 30000);
});
