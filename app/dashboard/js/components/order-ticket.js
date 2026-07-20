import { placeOrder, getQuote } from "../api.js";

let currentSide = "BUY";

export function initializeOrderTicket() {

    bindEvents();

    loadCurrentPrice();

}

function bindEvents() {

    document
        .getElementById("orderSide")
        .addEventListener(
            "change",
            onSideChanged
        );

    [
        "orderPrice",
        "orderQuantity",
        "orderStopLoss",
        "orderTakeProfit"
    ].forEach(id => {

        document
            .getElementById(id)
            .addEventListener(
                "input",
                updateRiskReward
            );

    });

    document
        .getElementById("btnPlaceOrder")
        .addEventListener(
            "click",
            submitOrder
        );

}

async function loadCurrentPrice() {

    try {

        const quote = await getQuote();

        const price =
            currentSide === "BUY"
                ? quote.ask
                : quote.bid;

        document
            .getElementById("orderPrice")
            .value = price.toFixed(2);

        updateRiskReward();

    }
    catch (error) {

        console.error(error);

    }

}

function onSideChanged(event) {

    currentSide = event.target.value;

    loadCurrentPrice();

}

function getNumber(id) {

    return Number(
        document.getElementById(id).value || 0
    );

}

function buildOrderRequest() {

    return {

        symbol:
            document.getElementById("orderSymbol").value,

        action:
            currentSide,

        price:
            getNumber("orderPrice"),

        quantity:
            getNumber("orderQuantity"),

        stop_loss:
            getNumber("orderStopLoss"),

        take_profit:
            getNumber("orderTakeProfit")

    };

}

function validateOrder(order) {

    if (!order.symbol)
        return "Symbol is required.";

    if (order.quantity <= 0)
        return "Quantity must be greater than zero.";

    if (order.price <= 0)
        return "Price is invalid.";

    if (currentSide === "BUY") {

        if (order.stop_loss >= order.price)
            return "BUY Stop Loss must be below Entry.";

        if (order.take_profit <= order.price)
            return "BUY Take Profit must be above Entry.";

    }
    else {

        if (order.stop_loss <= order.price)
            return "SELL Stop Loss must be above Entry.";

        if (order.take_profit >= order.price)
            return "SELL Take Profit must be below Entry.";

    }

    return null;

}

function closeModal() {

    bootstrap.Modal
        .getInstance(
            document.getElementById("orderModal")
        )
        ?.hide();

}

function clearForm() {

    document.getElementById("orderQuantity").value = 1;

    document.getElementById("orderStopLoss").value = "";

    document.getElementById("orderTakeProfit").value = "";

}

async function submitOrder() {

    const order = buildOrderRequest();

    const validation = validateOrder(order);

    if (validation) {

        alert(validation);

        return;

    }

    try {

        const result = await placeOrder(order);

        alert(result.message);

        if (!result.success)
            return;

        closeModal();

        clearForm();

        window.dispatchEvent(
            new Event("dashboard-refresh")
        );

    }
    catch (error) {

        console.error(error);

        alert("Unable to place order.");

    }

}

function updateRiskReward() {

    const price = getNumber("orderPrice");

    const qty = getNumber("orderQuantity");

    const sl = getNumber("orderStopLoss");

    const tp = getNumber("orderTakeProfit");

    let risk = 0;

    let reward = 0;

    if (currentSide === "BUY") {

        risk = price - sl;

        reward = tp - price;

    }
    else {

        risk = sl - price;

        reward = price - tp;

    }

    risk = Math.max(0, risk);

    reward = Math.max(0, reward);

    document.getElementById("riskValue")
        .textContent = (risk * qty).toFixed(2);

    document.getElementById("rewardValue")
        .textContent = (reward * qty).toFixed(2);

    document.getElementById("rrValue")
        .textContent =
        `1 : ${risk > 0 ? (reward / risk).toFixed(2) : "0.00"}`;

}