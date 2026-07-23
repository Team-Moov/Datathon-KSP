import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet"

import "leaflet/dist/leaflet.css"

interface GwrDistrictPoint {
  district_id: number
  district_name: string
  gwr_coefficients: Record<string, number>
  composite_score: number | null
  lat: number | null
  lon: number | null
}

// Karnataka's approximate geographic center — used only as the initial map
// view, never as a stand-in for a missing district coordinate.
const KARNATAKA_CENTER: [number, number] = [15.0, 76.0]

function colorForScore(score: number | null): string {
  if (score === null) return "#9ca3af"
  if (score >= 0.66) return "#953f30"
  if (score >= 0.33) return "#b8863f"
  return "#5f6299"
}

/**
 * Statewide GWR view as centroid markers, not a polygon choropleth — this
 * platform has no district-boundary geometry to draw real polygons from, and
 * fabricating shapes would render as if they were authoritative Karnataka
 * district boundaries when they wouldn't be. Marker position is each
 * district's real case-data centroid (same source the GWR fit itself uses);
 * color encodes local model fit (composite_score / local R²), and every
 * factor's coefficient is in the popup.
 */
function GwrCentroidMap({ points }: { points: GwrDistrictPoint[] }) {
  const plottable = points.filter((point) => point.lat !== null && point.lon !== null)

  if (plottable.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No districts have both a GWR run and a derivable centroid yet.</p>
  }

  return (
    <MapContainer center={KARNATAKA_CENTER} zoom={7} scrollWheelZoom={false} className="h-[380px] w-full rounded-md">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {plottable.map((point) => (
        <CircleMarker
          key={point.district_id}
          center={[point.lat as number, point.lon as number]}
          radius={12}
          pathOptions={{ color: colorForScore(point.composite_score), fillColor: colorForScore(point.composite_score), fillOpacity: 0.55, weight: 1 }}
        >
          <Popup>
            <div className="text-xs">
              <p className="font-semibold">{point.district_name}</p>
              {point.composite_score !== null ? <p>Local fit (R²): {point.composite_score.toFixed(3)}</p> : null}
              <ul className="mt-1 space-y-0.5">
                {Object.entries(point.gwr_coefficients).map(([factor, value]) => (
                  <li key={factor}>
                    {factor.replace(/_/g, " ")}: {value >= 0 ? "+" : ""}
                    {value.toFixed(3)}
                  </li>
                ))}
              </ul>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}

export { GwrCentroidMap }
export type { GwrDistrictPoint }
