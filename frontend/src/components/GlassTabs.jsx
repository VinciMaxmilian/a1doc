import { useRef, useState, useEffect, useCallback } from 'react'

export default function GlassTabs({ tabs, active, onChange }) {
  const containerRef = useRef(null)
  const [pill, setPill] = useState({ left: 4, width: 0 })

  const updatePill = useCallback(() => {
    const container = containerRef.current
    if (!container) return
    const btn = container.querySelector('.tab-active')
    if (btn) setPill({ left: btn.offsetLeft, width: btn.offsetWidth })
  }, [active])

  useEffect(() => {
    updatePill()
    const ro = new ResizeObserver(updatePill)
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [updatePill])

  return (
    <div className="glass-tabs" ref={containerRef}>
      <div
        className="glass-tab-pill"
        style={{ left: pill.left, width: pill.width }}
      />
      {tabs.map(t => (
        <button
          key={t.key}
          className={`glass-tab-btn${active === t.key ? ' tab-active' : ''}`}
          onClick={() => onChange(t.key)}
        >
          {t.icon && <span style={{ fontSize: 15 }}>{t.icon}</span>}
          {t.label}
        </button>
      ))}
    </div>
  )
}
