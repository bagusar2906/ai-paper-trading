export function updateBacktestMarkers(
    series,
    markers
) {

    series.setMarkers(

        markers.map(m => ({

            time:
                Math.floor(
                    new Date(m.time).getTime()/1000
                ),

            position: m.position,

            color: m.color,

            shape: m.shape,

            text: m.text,

        }))

    );

}