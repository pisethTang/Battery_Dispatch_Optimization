import { Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    LabelList,
    Line,
    LineChart,
    ReferenceLine,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from 'recharts';
import type { BacktestDay, BacktestIndex, BacktestMethod, ForecastMethod } from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

// one colour per method, used in every chart; perfect foresight is always the dashed line
const METHODS: BacktestMethod[] = ["perfect_foresight", "naive", "lightgbm", "lstm"];
const FORECASTS: ForecastMethod[] = ["naive", "lightgbm", "lstm"];
const COLOUR: Record<BacktestMethod, string> = {
    perfect_foresight: "#e4e4e7",
    naive: "#f59e0b",
    lightgbm: "#3b82f6",
    lstm: "#ec4899",
};
const LABEL: Record<BacktestMethod, string> = {
    perfect_foresight: "Perfect foresight",
    naive: "Naive",
    lightgbm: "LightGBM",
    lstm: "LSTM",
};
const DASH: Partial<Record<BacktestMethod, string>> = { perfect_foresight: "6 4" };

const aud = (v: number) => `${v < 0 ? '-' : ''}$${Math.abs(v).toLocaleString('en-AU', { maximumFractionDigits: 0 })}`;
const price = (v: number) => `${v < 0 ? '-' : ''}$${Math.abs(Math.round(v))}`;
const tooltipStyle = {
    contentStyle: { backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px', fontSize: '12px' },
    itemStyle: { color: '#fafafa' },
};

function Legend() {
    return (
        <div className="flex flex-wrap gap-4 text-xs text-zinc-400">
            {METHODS.map((m) => (
                <span key={m} className="flex items-center gap-2">
                    <svg width="22" height="6">
                        <line x1="0" y1="3" x2="22" y2="3" stroke={COLOUR[m]} strokeWidth="2" strokeDasharray={DASH[m]} />
                    </svg>
                    {m === "perfect_foresight" ? "Perfect foresight / actual price" : LABEL[m]}
                </span>
            ))}
        </div>
    );
}

function StackedChart({ title, data, keys, unit, height, showXAxis, domain }: {
    title: string;
    data: Record<string, number | string>[];
    keys: Record<BacktestMethod, string>;
    unit: (v: number) => string;
    height: number;
    showXAxis: boolean;
    domain?: [number, number];
}) {
    return (
        <div>
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">{title}</p>
            <ResponsiveContainer width="100%" height={height}>
                <LineChart data={data} syncId="backtest" margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis dataKey="time" stroke="#52525b" fontSize={11} tickMargin={8} interval={5} hide={!showXAxis} />
                    <YAxis stroke="#52525b" fontSize={11} tickFormatter={unit} width={70} domain={domain ?? ['auto', 'auto']} allowDataOverflow={!!domain} />
                    <Tooltip {...tooltipStyle} formatter={(v) => unit(Number(v))} />
                    {METHODS.map((m) => (
                        <Line
                            key={m}
                            type={title.startsWith("Battery") ? "stepAfter" : "linear"}
                            dataKey={keys[m]}
                            name={LABEL[m]}
                            stroke={COLOUR[m]}
                            strokeDasharray={DASH[m]}
                            strokeWidth={m === "perfect_foresight" ? 2 : 1.6}
                            dot={false}
                            isAnimationActive={false}
                        />
                    ))}
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}

export default function Backtest() {
    const [index, setIndex] = useState<BacktestIndex | null>(null);
    const [selected, setSelected] = useState<string>("");
    const [day, setDay] = useState<BacktestDay | null>(null);
    const [error, setError] = useState<string>("");
    const [zoomPrice, setZoomPrice] = useState<boolean>(false);

    useEffect(() => {
        fetch(`${BASE_URL}/backtest/days`)
            .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
            .then((idx: BacktestIndex) => {
                setIndex(idx);
                setSelected(idx.best_day);
            })
            .catch((e) => setError(`Could not load backtest results (${e.message}).`));
    }, []);

    useEffect(() => {
        if (!selected) return;
        fetch(`${BASE_URL}/backtest/day/${selected}`)
            .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
            .then(setDay)
            .catch((e) => setError(`Could not load ${selected} (${e.message}).`));
    }, [selected]);

    const rows = useMemo(() => {
        if (!day) return [];
        return day.intervals.map((time, i) => {
            const row: Record<string, number | string> = { time, price_perfect_foresight: day.actual_price[i] };
            for (const f of FORECASTS) row[`price_${f}`] = day.forecast_price[f][i];
            for (const m of METHODS) {
                row[`soc_${m}`] = day.methods[m].soc_mwh[i];
                row[`cum_${m}`] = day.methods[m].cumulative_profit_aud[i];
            }
            return row;
        });
    }, [day]);

    const captureBars = useMemo(() => {
        if (!index) return [];
        return FORECASTS.map((m) => ({
            method: m,
            label: LABEL[m],
            capture: Math.round(index.summary.models[m].capture_rate * 1000) / 10,
        }));
    }, [index]);

    // zoomed price axis: fit the forecasts and the bulk of actual prices, letting rare spikes run off the top
    const zoomDomain = useMemo((): [number, number] | undefined => {
        if (!day) return undefined;
        const sorted = [...day.actual_price].sort((a, b) => a - b);
        const p90 = sorted[Math.floor(0.9 * (sorted.length - 1))];
        const all = [...day.actual_price, ...FORECASTS.flatMap((f) => day.forecast_price[f])];
        const hi = Math.max(p90, ...FORECASTS.flatMap((f) => day.forecast_price[f]));
        return [Math.floor(Math.min(0, ...all) / 50) * 50, Math.ceil((hi * 1.15) / 50) * 50];
    }, [day]);

    const dates = index?.days.map((d) => d.date) ?? [];
    const keysFor = (prefix: string) =>
        Object.fromEntries(METHODS.map((m) => [m, `${prefix}_${m}`])) as Record<BacktestMethod, string>;

    const pickDate = (value: string) => {
        if (dates.includes(value)) {
            setError("");
            setSelected(value);
        }
    };

    return (
        <div className="flex h-screen bg-[#0f0f0f] text-zinc-100 font-sans antialiased">
            {/* LEFT SIDEBAR */}
            <div className="w-80 border-r border-zinc-800 bg-[#0f0f0f] p-6 flex flex-col gap-6 overflow-y-auto">
                <div>
                    <a href="#/" className="text-xs text-zinc-500 hover:text-zinc-300">← Live simulation</a>
                    <h1 className="text-2xl font-semibold text-white tracking-tight mt-3">Forecast Backtest</h1>
                    <p className="text-sm text-zinc-500 mt-1">
                        SA1 day-ahead forecasts scheduled by the same LP, scored on actual prices
                    </p>
                </div>

                {index && (
                    <>
                        <div className="space-y-2 text-sm text-zinc-400">
                            <p>Test days: <span className="text-zinc-200">{index.summary.Z_test_days}</span></p>
                            <p>Period: <span className="text-zinc-200">{index.summary.split.test[0]} → {index.summary.split.test[1]}</span></p>
                            <p>Battery: <span className="text-zinc-200">{index.summary.battery.capacity_mwh} MWh / {index.summary.battery.max_mw} MW / {index.summary.battery.efficiency * 100}%</span></p>
                        </div>

                        <div className="space-y-3">
                            <label className="text-sm font-medium text-zinc-300" htmlFor="bt-date">Test day</label>
                            <input
                                id="bt-date"
                                type="date"
                                min={dates[0]}
                                max={dates[dates.length - 1]}
                                value={selected}
                                onChange={(e) => pickDate(e.target.value)}
                                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 [color-scheme:dark]"
                            />
                            <div className="grid grid-cols-1 gap-2">
                                {([
                                    ["best_day", "Best day"],
                                    ["worst_day", "Worst day"],
                                    ["biggest_spike_day", "Biggest spike day"],
                                ] as const).map(([key, label]) => (
                                    <button
                                        key={key}
                                        onClick={() => pickDate(index[key])}
                                        title={index.definitions[key]}
                                        className={`text-sm py-2 px-3 rounded-lg border transition-colors text-left ${selected === index[key]
                                            ? 'bg-white text-black border-white'
                                            : 'border-zinc-800 text-zinc-300 hover:bg-zinc-900'}`}
                                    >
                                        {label} <span className="opacity-60">· {index[key]}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </>
                )}
            </div>

            {/* MAIN CONTENT AREA */}
            <div className="flex-1 p-6 flex flex-col gap-6 overflow-y-auto bg-[#0f0f0f]">
                {error && <p className="text-sm text-red-400">{error}</p>}
                {!index && !error && (
                    <div className="flex-1 flex items-center justify-center text-zinc-500 gap-2">
                        <Loader2 className="animate-spin" size={18} /> Loading backtest results...
                    </div>
                )}

                {day && (
                    <>
                        {/* per-day KPI cards */}
                        <div className="grid grid-cols-4 gap-4">
                            {METHODS.map((m) => {
                                const profit = day.methods[m].profit_aud;
                                const pf = day.methods.perfect_foresight.profit_aud;
                                return (
                                    <div key={m} className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-lg">
                                        <p className="text-xs font-medium uppercase tracking-wide" style={{ color: COLOUR[m] }}>{LABEL[m]}</p>
                                        <p className="text-lg font-medium mt-1 text-white">{aud(profit)}</p>
                                        <p className="text-xs text-zinc-600 mt-0.5">
                                            {m === "perfect_foresight" ? "upper bound for this day" : pf > 0 ? `${Math.round((100 * profit) / pf)}% of perfect foresight` : "—"}
                                        </p>
                                    </div>
                                );
                            })}
                        </div>

                        <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-6 flex flex-col gap-5">
                            <div className="flex justify-between items-center flex-wrap gap-3">
                                <h2 className="text-sm font-medium text-zinc-400">{day.date} (AEST, 30-minute intervals)</h2>
                                <Legend />
                            </div>
                            <label className="flex items-center gap-2 text-xs text-zinc-400 -mb-3 self-end cursor-pointer">
                                <input type="checkbox" checked={zoomPrice} onChange={(e) => setZoomPrice(e.target.checked)} className="accent-white" />
                                Zoom price axis (clip spikes)
                            </label>
                            <StackedChart title="Price: actual vs day-ahead forecast (AUD/MWh)" data={rows} keys={keysFor("price")} unit={price} height={220} showXAxis={false} domain={zoomPrice ? zoomDomain : undefined} />
                            <StackedChart title="Battery state of charge (MWh)" data={rows} keys={keysFor("soc")} unit={(v) => `${v}`} height={170} showXAxis={false} domain={index ? [0, index.summary.battery.capacity_mwh] : undefined} />
                            <StackedChart title="Cumulative profit at actual prices (AUD)" data={rows} keys={keysFor("cum")} unit={aud} height={190} showXAxis />
                        </div>
                    </>
                )}

                {index && (
                    <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-6">
                        <h2 className="text-sm font-medium text-zinc-400">Capture rate across all {index.summary.Z_test_days} test days</h2>
                        <p className="text-xs text-zinc-600 mt-1 mb-4">
                            Sum of realised revenue ÷ sum of perfect-foresight revenue ({aud(index.summary.perfect_foresight_aud)}). Dashed line = perfect foresight (100%).
                        </p>
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={captureBars} layout="vertical" margin={{ top: 0, right: 50, left: 10, bottom: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
                                <XAxis type="number" domain={[(dataMin: number) => Math.min(0, Math.floor(dataMin)), 100]} stroke="#52525b" fontSize={11} tickFormatter={(v) => `${v}%`} />
                                <YAxis type="category" dataKey="label" stroke="#52525b" fontSize={12} width={80} />
                                <ReferenceLine x={100} stroke={COLOUR.perfect_foresight} strokeDasharray={DASH.perfect_foresight} />
                                <Bar dataKey="capture" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                                    {captureBars.map((b) => <Cell key={b.method} fill={COLOUR[b.method]} />)}
                                    <LabelList dataKey="capture" position="right" fill="#d4d4d8" fontSize={12} formatter={(v) => `${v}%`} />
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>
        </div>
    );
}
