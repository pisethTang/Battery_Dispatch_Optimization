import { Loader2 } from 'lucide-react';
import { useState } from 'react';
import {
    Bar,
    CartesianGrid,
    ComposedChart,
    Legend,
    Line,
    ResponsiveContainer,
    Tooltip,
    XAxis, YAxis
} from 'recharts';
import type { ScheduleAction } from './types';

// Loading Overlay Component - Similar to Render's cold start page
function LoadingOverlay() {
    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center">
            <div className="text-center max-w-md px-6">
                <div className="relative w-16 h-16 mx-auto mb-6">
                    <div className="absolute inset-0 border-2 border-zinc-700 rounded-full"></div>
                    <div className="absolute inset-0 border-2 border-white rounded-full border-t-transparent animate-spin"></div>
                </div>
                <h3 className="text-xl font-medium text-white mb-2">
                    Starting optimization engine...
                </h3>
                <p className="text-zinc-400 text-sm leading-relaxed">
                    This may take a few seconds while we wake up the backend service and fetch live market data from AEMO.
                </p>
                <div className="mt-6 flex items-center justify-center gap-2 text-xs text-zinc-500">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                    Connecting to server
                </div>
            </div>
        </div>
    );
}

export default function App() {
    const [capacity, setCapacity] = useState(5.0);
    const [maxMw, setMaxMw] = useState(2.5);
    const [schedule, setSchedule] = useState<ScheduleAction[]>([]);
    const [profit, setProfit] = useState(0);
    const [cycledEnergy, setCycledEnergy] = useState(0);
    const [isOptimizing, setIsOptimizing] = useState<boolean>(false);

    const handleRunOptimization = async () => {
        setIsOptimizing(true);
        const base_url = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

        try {
            const payload = {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    "capacity_mwh": capacity,
                    "max_mw": maxMw,
                    efficiency: 0.9
                })
            };
            const response = await fetch(`${base_url}/simulate`, payload);
            const result = await response.json();

            if (result.optimization_status === "Optimal") {
                setSchedule(result.schedule);
                setProfit(result.total_profit_aud);
                const totalCharged = result.schedule.reduce(
                    (sum: number, block: ScheduleAction) => sum + block.charge_mw * 0.5, 0
                );
                setCycledEnergy(totalCharged);
            } else {
                console.error("Backend error: ", result.message);
            }
        } catch (error) {
            console.error("Network error: ", error);
        } finally {
            setIsOptimizing(false);
        }
    };

    return (
        <div className="flex h-screen bg-[#0f0f0f] text-zinc-100 font-sans antialiased">
            {isOptimizing && <LoadingOverlay />}

            {/* LEFT SIDEBAR */}
            <div className="w-80 border-r border-zinc-800 bg-[#0f0f0f] p-6 flex flex-col">
                <div className="mb-8">
                    <h1 className="text-2xl font-semibold text-white tracking-tight">
                        Battery Dispatch
                    </h1>
                    <p className="text-sm text-zinc-500 mt-1">SA1 Region Optimization</p>
                </div>

                <div className="flex flex-col gap-6">
                    <div className="space-y-3">
                        <div className="flex justify-between items-center">
                            <label className="text-sm font-medium text-zinc-300">Battery Capacity</label>
                            <span className="text-sm text-zinc-400">{capacity} MWh</span>
                        </div>
                        <input
                            type="range"
                            min="1"
                            max="10"
                            step="0.5"
                            value={capacity}
                            onChange={(e) => setCapacity(parseFloat(e.target.value))}
                            className="w-full accent-white"
                        />
                    </div>

                    <div className="space-y-3">
                        <div className="flex justify-between items-center">
                            <label className="text-sm font-medium text-zinc-300">Max Power Output</label>
                            <span className="text-sm text-zinc-400">{maxMw} MW</span>
                        </div>
                        <input
                            type="range"
                            min="0.5"
                            max="5"
                            step="0.5"
                            value={maxMw}
                            onChange={(e) => setMaxMw(parseFloat(e.target.value))}
                            className="w-full accent-white"
                        />
                    </div>
                </div>

                <button
                    onClick={handleRunOptimization}
                    disabled={isOptimizing}
                    className="mt-auto bg-white hover:bg-zinc-200 disabled:bg-zinc-700 disabled:text-zinc-400 text-black font-medium py-3 px-4 rounded-lg transition-colors flex justify-center items-center gap-2"
                >
                    {isOptimizing ? (
                        <>
                            <Loader2 className="animate-spin" size={18} />
                            Processing...
                        </>
                    ) : (
                        "Run Optimization"
                    )}
                </button>
            </div>

            {/* MAIN CONTENT AREA */}
            <div className="flex-1 p-6 flex flex-col gap-6 overflow-y-auto bg-[#0f0f0f]">

                {/* KPI CARDS - Clean, no icons */}
                <div className="grid grid-cols-3 gap-4">
                    <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-lg">
                        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Status</p>
                        <p className={`text-lg font-medium mt-1 ${schedule.length > 0 ? 'text-green-400' : 'text-zinc-300'}`}>
                            {schedule.length > 0 ? "Optimal" : "Waiting"}
                        </p>
                    </div>
                    <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-lg">
                        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Projected Profit</p>
                        <p className="text-lg font-medium mt-1 text-white">
                            ${profit.toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </p>
                        <p className="text-xs text-zinc-600 mt-0.5">24 hour forecast</p>
                    </div>
                    <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-lg">
                        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Energy Cycled</p>
                        <p className="text-lg font-medium mt-1 text-white">
                            {cycledEnergy.toFixed(1)} <span className="text-zinc-500 text-sm">MWh</span>
                        </p>
                    </div>
                </div>

                {/* THE CHART */}
                <div className="flex-1 bg-zinc-900/30 border border-zinc-800 rounded-lg p-6 min-h-[400px] flex flex-col">
                    <h2 className="text-sm font-medium text-zinc-400 mb-6">
                        Dispatch Schedule vs. Spot Price
                    </h2>

                    {schedule.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-zinc-600">
                            <p className="text-sm">Configure battery parameters and click Run Optimization</p>
                            <p className="text-xs mt-1">to fetch live market data from AEMO</p>
                        </div>
                    ) : (
                        <div className="flex-1 w-full min-h-0">
                            <ResponsiveContainer width="100%" height="100%">
                                <ComposedChart data={schedule} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                                    <XAxis
                                        dataKey="timestamp"
                                        stroke="#52525b"
                                        fontSize={11}
                                        tickMargin={8}
                                        tickFormatter={(val) => val.substring(11, 16)}
                                    />
                                    <YAxis
                                        yAxisId="left"
                                        stroke="#52525b"
                                        fontSize={11}
                                        tickFormatter={(val) => `$${val}`}
                                    />
                                    <YAxis
                                        yAxisId="right"
                                        orientation="right"
                                        stroke="#52525b"
                                        fontSize={11}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: '#18181b',
                                            borderColor: '#27272a',
                                            borderRadius: '8px',
                                            fontSize: '12px'
                                        }}
                                        itemStyle={{ color: '#fafafa' }}
                                        labelFormatter={(label) => `Time: ${label.substring(11, 16)}`}
                                    />
                                    <Legend
                                        wrapperStyle={{ paddingTop: '20px', fontSize: '12px' }}
                                    />
                                    <Bar
                                        yAxisId="right"
                                        dataKey="soc_mwh"
                                        name="State of Charge (MWh)"
                                        fill="#3b82f6"
                                        radius={[2, 2, 0, 0]}
                                        opacity={0.7}
                                    />
                                    <Line
                                        yAxisId="left"
                                        type="monotone"
                                        dataKey="price_aud_mwh"
                                        name="Price ($/MWh)"
                                        stroke="#22c55e"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                </ComposedChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
}
