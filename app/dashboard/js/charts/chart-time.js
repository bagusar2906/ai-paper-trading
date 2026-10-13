// Format chart labels in the user's timezone without shifting candle timestamps.
export const CHART_TIME_ZONE = "Asia/Jakarta";

function formatter(options) {
    return new Intl.DateTimeFormat("en-GB", {
        timeZone: CHART_TIME_ZONE,
        ...options,
    });
}

const year = formatter({ year: "numeric" });
const month = formatter({ month: "short" });
const day = formatter({ day: "2-digit", month: "short" });
const minute = formatter({ hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const second = formatter({ hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const dateTime = formatter({
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

function chartDate(time) {
    if (typeof time === "number") return new Date(time * 1000);
    if (typeof time === "string") return new Date(`${time}T00:00:00Z`);
    return new Date(Date.UTC(time.year, time.month - 1, time.day));
}

export function formatChartTime(time) {
    return `${dateTime.format(chartDate(time))} WIB`;
}

export function formatChartTick(time, tickMarkType) {
    // Lightweight Charts: Year, Month, DayOfMonth, Time, TimeWithSeconds.
    const formats = [year, month, day, minute, second];
    return (formats[tickMarkType] || minute).format(chartDate(time));
}
