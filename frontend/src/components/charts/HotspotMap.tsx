import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet"

import "leaflet/dist/leaflet.css"

import type { HotspotForecastCell } from "@/features/trends/trendsApi"

interface HotspotMapProps {
  cells: HotspotForecastCell[]
  centerLat: number
  centerLng: number
}

function radiusForRate(rate: number, maxRate: number): number {
  const minRadius = 4
  const maxRadius = 22
  if (maxRate <= 0) return minRadius
  return minRadius + (rate / maxRate) * (maxRadius - minRadius)
}

/**
 * CircleMarker only (no default Leaflet pin icon) — avoids the well-known
 * bundler asset-path breakage with L.Icon.Default and keeps the visual weight
 * proportional to predicted_rate, which a generic pin can't communicate.
 */
function HotspotMap({ cells, centerLat, centerLng }: HotspotMapProps) {
  const maxRate = Math.max(...cells.map((cell) => cell.predicted_rate), 0.001)

  return (
    <MapContainer center={[centerLat, centerLng]} zoom={12} scrollWheelZoom={false} className="h-[420px] w-full rounded-md">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {cells.map((cell, index) => (
        <CircleMarker
          key={`${cell.lat_center}-${cell.lng_center}-${index}`}
          center={[cell.lat_center, cell.lng_center]}
          radius={radiusForRate(cell.predicted_rate, maxRate)}
          pathOptions={{ color: "#953f30", fillColor: "#b1503f", fillOpacity: 0.45, weight: 1 }}
        >
          <Popup>
            <div className="text-xs">
              <p className="font-semibold">Predicted rate: {cell.predicted_rate.toFixed(3)}</p>
              <p>Background: {cell.background_component.toFixed(3)}</p>
              <p>Near-repeat: {cell.near_repeat_component.toFixed(3)}</p>
              <p className="text-zinc-500">{cell.forecast_date}</p>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}

export { HotspotMap }
