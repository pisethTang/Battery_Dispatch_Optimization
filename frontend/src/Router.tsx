import { useEffect, useState } from 'react'
import App from './App.tsx'
import Backtest from './Backtest.tsx'

// hash routing keeps the S3/CloudFront static hosting unchanged: #/backtest -> Backtest, anything else -> live App
export default function Router() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash.startsWith('#/backtest') ? <Backtest /> : <App />
}
