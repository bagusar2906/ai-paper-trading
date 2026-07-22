let markerPrimitive = null;

export function updateMarkers(series, markers) {

    if (!window.LightweightChartsPluginMarkers)
        return;

    if (markerPrimitive) {
        series.detachPrimitive(markerPrimitive);
        markerPrimitive = null;
    }

}