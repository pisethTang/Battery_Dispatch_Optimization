import { Activity, DollarSign, Zap } from 'lucide-react';
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



// --- 1. MOCK DATA ---
import { mockSchedule } from './mock_data';

export default function App() {
  // State for the left sidebar controls
  const [capacity, setCapacity] = useState(5.0);
  const [maxMw, setMaxMw] = useState(2.5);

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 font-sans">
      
      {/* LEFT SIDEBAR: Controls */}
      <div className="w-80 border-r border-gray-800 bg-gray-900 p-6 flex flex-col gap-6 shadow-xl z-10">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
            OptiGrid Analyzer
          </h1>
          <p className="text-sm text-gray-400 mt-1">SA1 Dispatch Optimization</p>
        </div>

        <div className="flex flex-col gap-4 mt-4">
          <label className="flex flex-col gap-2">
            <span className="text-sm font-semibold text-gray-300 border-b border-gray-800 pb-1">Battery Capacity (MWh)</span>
            <input 
              type="range" min="1" max="10" step="0.5" 
              value={capacity} onChange={(e) => setCapacity(parseFloat(e.target.value))}
              className="accent-blue-500"
            />
            <span className="text-right text-xs font-mono text-blue-400">{capacity} MWh</span>
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-semibold text-gray-300 border-b border-gray-800 pb-1">Max Power (MW)</span>
            <input 
              type="range" min="0.5" max="5" step="0.5" 
              value={maxMw} onChange={(e) => setMaxMw(parseFloat(e.target.value))}
              className="accent-emerald-500"
            />
            <span className="text-right text-xs font-mono text-emerald-400">{maxMw} MW</span>
          </label>
        </div>

        <button className="mt-auto bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg transition-colors shadow-lg shadow-blue-900/20">
          Run Optimization
        </button>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 p-8 flex flex-col gap-8 overflow-y-auto">
        
        {/* KPI CARDS */}
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl shadow-lg flex items-center gap-4">
            <div className="p-3 bg-blue-900/30 rounded-lg text-blue-400"><Activity size={24} /></div>
            <div>
              <p className="text-sm text-gray-400">Status</p>
              <p className="text-xl font-bold text-gray-100">Optimal</p>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl shadow-lg flex items-center gap-4">
            <div className="p-3 bg-emerald-900/30 rounded-lg text-emerald-400"><DollarSign size={24} /></div>
            <div>
              <p className="text-sm text-gray-400">Projected Profit (24h)</p>
              <p className="text-xl font-bold text-emerald-400">$860.03</p>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl shadow-lg flex items-center gap-4">
            <div className="p-3 bg-purple-900/30 rounded-lg text-purple-400"><Zap size={24} /></div>
            <div>
              <p className="text-sm text-gray-400">Total Cycled Energy</p>
              <p className="text-xl font-bold text-gray-100">5.0 MWh</p>
            </div>
          </div>
        </div>

        {/* THE CHART */}
        <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl shadow-lg flex-1 min-h-[400px] flex flex-col">
          <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
            Dispatch Schedule vs. Spot Price
          </h2>
          <div className="flex-1 w-full h-full">
            <ResponsiveContainer width="100%" height="100%">
              {/* ComposedChart allows mixing Lines and Bars on the same graph */}
              <ComposedChart data={mockSchedule} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                <XAxis dataKey="timestamp" stroke="#9CA3AF" fontSize={12} tickMargin={10} />
                
                {/* Left Y-Axis for Price */}
                <YAxis yAxisId="left" stroke="#10B981" fontSize={12} tickFormatter={(val) => `$${val}`} />
                {/* Right Y-Axis for State of Charge */}
                <YAxis yAxisId="right" orientation="right" stroke="#3B82F6" fontSize={12} tickFormatter={(val) => `${val}MWh`} />
                
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '8px' }}
                  itemStyle={{ color: '#E5E7EB' }}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />

                {/* The Blue Bars: How full the tank is */}
                <Bar yAxisId="right" dataKey="soc_mwh" name="State of Charge (MWh)" fill="#3B82F6" radius={[4, 4, 0, 0]} opacity={0.8} />
                
                {/* The Green Line: The volatile grid price */}
                <Line yAxisId="left" type="monotone" dataKey="price_aud_mwh" name="Price ($/MWh)" stroke="#10B981" strokeWidth={3} dot={{ r: 4, fill: '#10B981' }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </div>
  );
}