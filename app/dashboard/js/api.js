async function request(url, options = {}) {

    const response = await fetch(url, {

        headers: {
            "Content-Type": "application/json",
        },

        ...options,

    });

    if (!response.ok) {

        let detail = response.statusText;
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        }
        catch (_) {
            // Some proxy/server failures do not return JSON.
        }

        throw new Error(
            `HTTP ${response.status}: ${detail}`
        );

    }

    return await response.json();

}

// -----------------------------------------------------
// Dashboard
// -----------------------------------------------------

export async function getDashboard() {

    return request("/dashboard");

}

export async function adjustFunds(amount) {

    return request("/account/funds", {

        method: "POST",
        body: JSON.stringify({ amount }),

    });

}

export async function getChart() {

    return request("/chart");

}

export async function getModels() { return request("/models"); }
export async function getActiveSignalModel() { return request("/models/signal-model"); }
export async function getModelImprovementReport() { return request("/models/improvement-report"); }
export async function getModelExperimentPlan(parameters) {
    const query = new URLSearchParams(parameters);
    return request(`/models/experiment-plan?${query}`);
}
export async function getModelHealth() { return request("/models/health"); }
export async function runModelMonitoringCheck() { return request("/models/monitoring-check", { method: "POST" }); }
export async function getModelReviewGuidance(id) { return request(`/models/${encodeURIComponent(id)}/review-guidance`, { method: "POST" }); }
export async function analyzeModel(id) { return request(`/models/${encodeURIComponent(id)}/analyze`, { method: "POST" }); }
export async function getModelReviewHistory(id) { return request(`/models/${encodeURIComponent(id)}/review-history`); }
export async function askModelLab(message) { return request("/models/chat", { method: "POST", body: JSON.stringify({ message }) }); }
export async function trainCandidate(payload) {
    return request("/models/train", { method: "POST", body: JSON.stringify(payload) });
}

export async function getSelfTrainingStatus() { return request("/models/self-training"); }
export async function configureSelfTraining(payload) {
    return request("/models/self-training", { method: "PUT", body: JSON.stringify(payload) });
}
export async function promoteModel(id, reviewer, rationale) {
    return request(`/models/${encodeURIComponent(id)}/promote`, { method: "POST", body: JSON.stringify({ reviewer, rationale }) });
}
export async function rollbackModel(id, reviewer, rationale) {
    return request(`/models/${encodeURIComponent(id)}/rollback`, { method: "POST", body: JSON.stringify({ reviewer, rationale }) });
}
export async function deleteModel(id, reviewer, rationale) {
    return request(`/models/${encodeURIComponent(id)}`, { method: "DELETE", body: JSON.stringify({ reviewer, rationale }) });
}

// -----------------------------------------------------
// Quotes
// -----------------------------------------------------

export async function getQuote(symbol = "XAUUSD") {

    return request(
        `/quote?symbol=${encodeURIComponent(symbol)}`
    );

}

// -----------------------------------------------------
// Orders
// -----------------------------------------------------

export async function placeOrder(order) {

    return request("/orders", {

        method: "POST",

        body: JSON.stringify(order),

    });

}

export async function closePosition(id) {

    return request(`/positions/${id}/close`, {

        method: "POST",

    });

}


export async function updatePosition(id, body) {

    return request(
        `/positions/${id}`,
        {
            method: "PUT",
            body: JSON.stringify(body),
        }
    );

}

// -----------------------------------------------------
// Backtest
// -----------------------------------------------------

export async function startBacktest(backtestRequest) {

    return request("/backtest/start", {

        method: "POST",

        body: JSON.stringify(backtestRequest),

    });

}

export async function getBacktestProgress(jobId) {

    return request(`/backtest/progress/${jobId}`);

}

export async function cancelBacktest(jobId) {

    return request(`/backtest/cancel/${jobId}`, {

        method: "POST",

    });

}

export async function getStrategies() {

    const response =
        await fetch("/strategy");

    return response.json();

}

// -----------------------------------------------------  
// Trading Mode
// -----------------------------------------------------

export async function getSettings() {

    return request("/settings");

}

export async function updateSettings(settings) {

    return request("/settings", {

        method: "PUT",

        body: JSON.stringify(settings),

    });

}

export async function getStrategyProfiles() {

    const response = await fetch(
        "/strategy-profiles"
    );

    return response.json();
}

export async function getStrategyProfile(id) {

    const response = await fetch(
        `/strategy-profiles/${id}`
    );

    return response.json();
}

export async function createStrategyProfile(data) {

    const response = await fetch(
        "/strategy-profiles",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(data),
        }
    );

    return response.json();
}

export async function updateStrategyProfile(id, data) {

    const response = await fetch(
        `/strategy-profiles/${id}`,
        {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(data),
        }
    );

    return response.json();
}

export async function deleteStrategyProfile(id) {

    const response = await fetch(
        `/strategy-profiles/${id}`,
        {
            method: "DELETE",
        }
    );

    return response.json();
}
