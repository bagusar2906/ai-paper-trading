export async function getDashboard() {

    const response = await fetch("/dashboard");

    if (!response.ok)
        throw new Error("Failed to load dashboard.");

    return await response.json();
}

export async function getChart() {

    const response = await fetch("/chart");

    if (!response.ok)
        throw new Error("Failed to load chart.");

    return await response.json();
}