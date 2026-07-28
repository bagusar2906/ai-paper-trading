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

    const response =
        await fetch("/strategy", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(request)

        });

    return response.json();

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