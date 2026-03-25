import { Activity, DollarSign, Loader2, Zap } from 'lucide-react';
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

// importing types 
// 'ScheduleAction' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.ts(1484)
// import { ScheduleAction } from './types';

// To fix this error when verbatimModuleSyntax is enabled in TypeScript 5.0+, you must explicitly tell TypeScript to remove the import at runtime by adding the type keyword to the import statement. 
import type { ScheduleAction } from './types';


// --- 1. MOCK DATA ---
// We use fake data that perfectly matches your backend JSON contract to test the UI safely.




export default function App() {
    // State for the left sidebar controls
    const [capacity, setCapacity] = useState(5.0);
    const [maxMw, setMaxMw] = useState(2.5);

    //   data states 
    const [schedule, setSchedule] = useState<ScheduleAction[]>([]);
    const [profit, setProfit] = useState(0);
    const [cycledEnergy, setCycledEnergy] = useState(0);

    // 3. Loading State
    const [isOptimizing, setIsOptimizing] = useState<boolean>(false);


    // 4. network request 
    const handleRunOptimization = async () => {
        setIsOptimizing(true); 


        // Fallback to localhost just in case the env variable is missing
        // const base_url = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";
        const base_url = "http://localhost:8000/api/v1";
        


        
        try {
            const payload = {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    "capacity_mwh": capacity,
                    "max_mw": maxMw, 
                    efficiency: 0.9 // hardcorded for efficiency for now 
                })
            };
            const response = await fetch(`${base_url}/simulate`, payload);
            console.log("response:", response);

            const result = await response.json();

            console.log("Raw backend result:", result); // Let's print the actual data!
            
            
            
            if (result.optimization_status === "Optimal"){
                console.log("Success");
                setSchedule(result.schedule);
                setProfit(result.total_profit_aud);
                // Calculate total energy moved (just summing up the charge amounts)
                const totalCharged = result.schedule.reduce(
                    (sum: number, 
                    block: ScheduleAction) => 
                        
                    sum + block.charge_mw * 0.5, 0
                );
                setCycledEnergy(totalCharged);
            } else {
                console.log("Error: ", result.message   );
                console.error("Backend error: ", result.message);
            }
        } catch (error){
            console.error("Network error: ", error);
        } finally {
            setIsOptimizing(false);
        }
    };

    return (
    <div className="flex h-screen bg-gray-950 text-gray-100 font-sans">
      
      {/* LEFT SIDEBAR */}
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

        <button 
          onClick={handleRunOptimization}
          disabled={isOptimizing}
          className="mt-auto bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:text-blue-300 text-white font-bold py-3 rounded-lg transition-colors shadow-lg shadow-blue-900/20 flex justify-center items-center gap-2"
        >
          {isOptimizing ? <><Loader2 className="animate-spin" size={20} /> Optimizing...</> : "Run Optimization"}
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
              <p className="text-xl font-bold text-gray-100">{schedule.length > 0 ? "Optimal" : "Waiting"}</p>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl shadow-lg flex items-center gap-4">
            <div className="p-3 bg-emerald-900/30 rounded-lg text-emerald-400"><DollarSign size={24} /></div>
            <div>
              <p className="text-sm text-gray-400">Projected Profit (24h)</p>
              <p className="text-xl font-bold text-emerald-400">${profit.toFixed(2)}</p>
            </div>
          </div>
          <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl shadow-lg flex items-center gap-4">
            <div className="p-3 bg-purple-900/30 rounded-lg text-purple-400"><Zap size={24} /></div>
            <div>
              <p className="text-sm text-gray-400">Total Cycled Energy</p>
              <p className="text-xl font-bold text-gray-100">{cycledEnergy.toFixed(1)} MWh</p>
            </div>
          </div>
        </div>

        {/* THE CHART */}
        <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl shadow-lg flex-1 min-h-[400px] flex flex-col relative">
          <h2 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
            Dispatch Schedule vs. Spot Price
          </h2>
          
          {schedule.length === 0 ? (
             <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500">
               <Activity size={48} className="mb-4 opacity-20" />
               <p>Adjust parameters and click "Run Optimization" to pull live AEMO data.</p>
             </div>
          ) : (
            <div className="flex-1 w-full h-full">
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                <ComposedChart data={schedule} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                  {/* We format the ISO timestamp to just show Time (e.g., 14:30) */}
                  <XAxis dataKey="timestamp" stroke="#9CA3AF" fontSize={12} tickMargin={10} tickFormatter={(val) => val.substring(11, 16)} />
                  <YAxis yAxisId="left" stroke="#10B981" fontSize={12} tickFormatter={(val) => `$${val}`} />
                  <YAxis yAxisId="right" orientation="right" stroke="#3B82F6" fontSize={12} tickFormatter={(val) => `${val}`} />
                  
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '8px' }}
                    itemStyle={{ color: '#E5E7EB' }}
                    labelFormatter={(label) => `Time: ${label.substring(11, 16)}`}
                  />
                  <Legend wrapperStyle={{ paddingTop: '20px' }} />

                  <Bar yAxisId="right" dataKey="soc_mwh" name="State of Charge (MWh)" fill="#3B82F6" radius={[4, 4, 0, 0]} opacity={0.8} />
                  <Line yAxisId="left" type="monotone" dataKey="price_aud_mwh" name="Price ($/MWh)" stroke="#10B981" strokeWidth={3} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}