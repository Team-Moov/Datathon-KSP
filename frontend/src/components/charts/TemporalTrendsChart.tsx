import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

export interface DayOfWeekPoint {
  day: string
  count: number
  pct: number
}

export interface MonthlyPoint {
  month: string
  count: number
  pct: number
}

export interface HourOfDayPoint {
  hour: number
  count: number
  pct: number
}

export interface TemporalTrendsData {
  status: "ok" | "insufficient_data"
  total_cases: number
  day_of_week: DayOfWeekPoint[]
  weekday_vs_weekend: { weekday_pct: number; weekend_pct: number } | null
  monthly: MonthlyPoint[]
  hour_of_day: HourOfDayPoint[]
  hour_of_day_coverage_pct: number
}

function MiniBarChart({ data, xKey, color }: { data: readonly unknown[]; xKey: string; color: string }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data as Record<string, unknown>[]} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
        <XAxis dataKey={xKey} tick={{ fontSize: 10 }} stroke="currentColor" className="text-zinc-400" />
        <YAxis tick={{ fontSize: 10 }} stroke="currentColor" className="text-zinc-400" />
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} wrapperClassName="!glass-overlay" />
        <Bar dataKey="count" name="Cases" fill={color} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Real day-of-week / monthly / hour-of-day breakdown from actual case dates —
 * hour-of-day is honestly coverage-limited (see hour_of_day_coverage_pct), never
 * padded to look complete when most historical cases have no recorded time. */
function TemporalTrendsChart({ data }: { data: TemporalTrendsData }) {
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400">
        <span className="font-medium text-zinc-700 dark:text-zinc-300">{data.total_cases} cases</span>
        {data.weekday_vs_weekend ? (
          <span>
            {data.weekday_vs_weekend.weekday_pct}% weekday / {data.weekday_vs_weekend.weekend_pct}% weekend
          </span>
        ) : null}
      </div>

      <div>
        <p className="section-label mb-1.5">Day of week</p>
        <MiniBarChart data={data.day_of_week} xKey="day" color="#5f6299" />
      </div>

      <div>
        <p className="section-label mb-1.5">Monthly seasonality</p>
        <MiniBarChart data={data.monthly} xKey="month" color="#b8863f" />
      </div>

      <div>
        <p className="section-label mb-1.5">
          Hour of day <span className="font-normal text-zinc-400">({data.hour_of_day_coverage_pct}% of cases have a recorded time)</span>
        </p>
        {data.hour_of_day.length === 0 ? (
          <p className="px-1 text-xs text-zinc-400">
            No cases in this scope have a recorded time-of-occurrence yet. This chart populates as new cases record one.
          </p>
        ) : (
          <MiniBarChart
            data={data.hour_of_day.map((h) => ({ ...h, hour: `${h.hour}:00` }))}
            xKey="hour"
            color="#b1503f"
          />
        )}
      </div>
    </div>
  )
}

export { TemporalTrendsChart }
