async function request(url, options = {}) {

    const response = await fetch(url, {

        headers: {
            "Content-Type": "application/json",
        },

        ...options,

    });

    if (!response.ok) {

        throw new Error(
            `HTTP ${response.status}: ${response.statusText}`
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

export async function getChart() {

    return request("/chart");

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