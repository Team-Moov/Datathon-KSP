import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

interface TrendLineChartProps {
  data: readonly unknown[]
  xKey: string
  seriesKeys: { key: string; label: string; color: string }[]
  height?: number
}

function TrendLineChart({ data, xKey, seriesKeys, height = 280 }: TrendLineChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data as Record<string, unknown>[]} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
        <XAxis dataKey={xKey} tick={{ fontSize: 11 }} stroke="currentColor" className="text-zinc-400" />
        <YAxis tick={{ fontSize: 11 }} stroke="currentColor" className="text-zinc-400" />
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} wrapperClassName="!glass-overlay" />
        {seriesKeys.map((series) => (
          <Line
            key={series.key}
            type="monotone"
            dataKey={series.key}
            name={series.label}
            stroke={series.color}
            strokeWidth={2}
            dot={{ r: 2.5 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

export { TrendLineChart }
