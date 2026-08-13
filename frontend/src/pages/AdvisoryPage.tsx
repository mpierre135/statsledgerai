import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useParams } from 'react-router-dom'
import { Card, formatMoney } from '../components'
import { getClient, getIndustries, reasonableComp, taxSavings } from '../api'

export function AdvisoryPage() {
  const { clientId = '' } = useParams()
  const [entity, setEntity] = useState('')
  const [industries, setIndustries] = useState<any[]>([])
  const [net, setNet] = useState('145000')
  const [hours, setHours] = useState('1800')
  const [industry, setIndustry] = useState('531110')
  const [comp, setComp] = useState<any | null>(null)
  const [savings, setSavings] = useState<any | null>(null)
  const [augustaDays, setAugustaDays] = useState(10)
  const [augustaRate, setAugustaRate] = useState('400')
  const [sec179, setSec179] = useState('15000')

  useEffect(() => {
    getClient(clientId).then((c) => setEntity(c.entity_type))
    getIndustries().then(setIndustries)
  }, [clientId])

  const run = async () => {
    const c = await reasonableComp(clientId, {
      net_income: net,
      hours_worked: hours,
      industry_code: industry,
    })
    setComp(c)
    const s = await taxSavings(clientId, {
      net_income: net,
      proposed_salary: c.recommended_salary || '0',
      augusta_days: augustaDays,
      augusta_daily_rate: augustaRate,
      section_179: sec179,
    })
    setSavings(s)
  }

  const currentOptOption = useMemo(() => {
    if (!savings) return {}
    return {
      backgroundColor: 'transparent',
      textStyle: { color: '#94a3b8' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: savings.chart_current_vs_optimized.categories },
      yAxis: { type: 'value' },
      series: [
        {
          type: 'bar',
          data: savings.chart_current_vs_optimized.values.map(Number),
          itemStyle: { color: '#10B981' },
          barWidth: 48,
        },
      ],
    }
  }, [savings])

  const yoyOption = useMemo(() => {
    if (!savings?.cumulative_yoy?.length) return {}
    const years = savings.cumulative_yoy.map((y: any) => String(y.year))
    const strategies = Array.from(
      new Set(savings.cumulative_yoy.flatMap((y: any) => Object.keys(y.by_strategy))),
    ) as string[]
    const colors = ['#10B981', '#34D399', '#F59E0B', '#60A5FA', '#A78BFA']
    return {
      backgroundColor: 'transparent',
      textStyle: { color: '#94a3b8' },
      tooltip: { trigger: 'axis' },
      legend: { textStyle: { color: '#94a3b8' } },
      xAxis: { type: 'category', data: years },
      yAxis: { type: 'value' },
      series: strategies.map((s, i) => ({
        name: s,
        type: 'bar',
        stack: 'total',
        data: savings.cumulative_yoy.map((y: any) => Number(y.by_strategy[s] || 0)),
        itemStyle: { color: colors[i % colors.length] },
      })),
    }
  }, [savings])

  return (
    <div className="space-y-4">
      <Card title="Reasonable compensation wizard">
        {entity !== 's_corp' && (
          <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
            Enabled for S-Corp clients only. Current entity: {entity || '…'}
          </div>
        )}
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm">
            Net income
            <input className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" value={net} onChange={(e) => setNet(e.target.value)} />
          </label>
          <label className="text-sm">
            Hours worked
            <input className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" value={hours} onChange={(e) => setHours(e.target.value)} />
          </label>
          <label className="text-sm">
            Industry
            <select className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" value={industry} onChange={(e) => setIndustry(e.target.value)}>
              {industries.map((i) => (
                <option key={i.code} value={i.code}>
                  {i.title}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <label className="text-sm">
            Augusta days
            <input type="number" className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" value={augustaDays} onChange={(e) => setAugustaDays(Number(e.target.value))} />
          </label>
          <label className="text-sm">
            Augusta daily rate
            <input className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" value={augustaRate} onChange={(e) => setAugustaRate(e.target.value)} />
          </label>
          <label className="text-sm">
            Section 179
            <input className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" value={sec179} onChange={(e) => setSec179(e.target.value)} />
          </label>
        </div>
        <button className="mt-4 rounded-lg bg-emerald-500 px-4 py-2 text-sm text-white" onClick={run}>
          Calculate
        </button>
        {comp && (
          <div className="mt-4 rounded-xl border border-slate-200 p-4 text-sm dark:border-slate-700">
            {comp.enabled ? (
              <>
                <div className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">
                  Recommended salary {formatMoney(comp.recommended_salary)}
                </div>
                <div className="text-xs text-slate-500">
                  Range {formatMoney(comp.range_low)} – {formatMoney(comp.range_high)} · FTE {comp.fte}
                </div>
                <p className="mt-2 text-slate-600 dark:text-slate-300">{comp.rationale}</p>
              </>
            ) : (
              <p>{comp.message}</p>
            )}
            <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">{comp.disclaimer}</p>
          </div>
        )}
      </Card>

      {savings && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <div className="text-xs text-slate-500">Current liability</div>
              <div className="font-mono-amount text-xl">{formatMoney(savings.current_liability)}</div>
            </Card>
            <Card>
              <div className="text-xs text-slate-500">Optimized liability</div>
              <div className="font-mono-amount text-xl text-emerald-600">{formatMoney(savings.optimized_liability)}</div>
            </Card>
            <Card>
              <div className="text-xs text-slate-500">Total savings</div>
              <div className="font-mono-amount text-xl text-emerald-600">{formatMoney(savings.total_savings)}</div>
            </Card>
          </div>

          <Card title="Current vs optimized">
            <ReactECharts option={currentOptOption} style={{ height: 280 }} />
          </Card>

          <Card title="Cumulative year-over-year tax savings">
            <ReactECharts option={yoyOption} style={{ height: 320 }} />
            <ul className="mt-3 space-y-1 text-sm">
              {savings.strategies.map((s: any) => (
                <li key={s.strategy}>
                  <span className="font-medium">{s.strategy}</span>: {formatMoney(s.savings)} — {s.detail}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">{savings.disclaimer}</p>
          </Card>
        </>
      )}
    </div>
  )
}
