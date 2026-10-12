import { Activity, ChartLine } from 'lucide-react';

const TABS = [
    { href: '#/', label: 'Live', icon: Activity },
    { href: '#/backtest', label: 'Backtest', icon: ChartLine },
] as const;

// page switcher shown at the top of both sidebars
export default function NavTabs({ active }: { active: 'Live' | 'Backtest' }) {
    return (
        <nav className="grid grid-cols-2 gap-1 p-1 bg-zinc-900 border border-zinc-800 rounded-lg">
            {TABS.map(({ href, label, icon: Icon }) => (
                <a
                    key={label}
                    href={href}
                    aria-current={active === label ? 'page' : undefined}
                    className={`flex items-center justify-center gap-2 py-1.5 rounded-md text-sm font-medium transition-colors ${active === label
                        ? 'bg-white text-black'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800'}`}
                >
                    <Icon size={15} />
                    {label}
                </a>
            ))}
        </nav>
    );
}
