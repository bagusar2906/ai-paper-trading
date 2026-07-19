let markerPrimitive = null;

export function updateMarkers(series, markers) {

    if (!window.LightweightChartsPluginMarkers)
        return;

    if (markerPrimitive) {
        series.detachPrimitive(markerPrimitive);
        markerPrimitive = null;
    }

    markerPrimitive =
        LightweightChartsPluginMarkers.createSeriesMarkers(
            series,
            markers.map(m => ({
                time: Math.floor(new Date(m.time).getTime() / 1000),
                position: m.position,
                color: m.color,
                shape: m.shape,
                text: m.text,
            }))
        );
}