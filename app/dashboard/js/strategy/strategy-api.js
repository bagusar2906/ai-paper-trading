export async function getStrategies() {

    const response =
        await fetch("/strategy");

    return response.json();

}

export async function getStrategy(id) {

    const response =
        await fetch(`/strategy/${id}`);

    return response.json();

}

export async function createStrategy(request) {

    console.log("Request:", request);

    const response = await fetch("/strategy", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify(request)

    });

    const text = await response.text();

    console.log("Status:", response.status);
    console.log("Response:", text);

    if (!response.ok) {
        throw new Error(text);
    }

    return JSON.parse(text);
}

export async function updateStrategy(id, request) {

    const response =
        await fetch(`/strategy/${id}`, {

            method: "PUT",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(request)

        });

    return response.json();

}

export async function deleteStrategy(id) {

    await fetch(`/strategy/${id}`, {

        method: "DELETE"

    });

}

export async function getStrategyTypes() {

    const response =
        await fetch("/strategy/types");

    return response.json();

}

export async function getStrategySchema(type) {

    const response =
        await fetch(`/strategy/schema/${type}`);

    return response.json();

}