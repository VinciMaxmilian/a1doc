import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom não implementa ResizeObserver, e o GlassTabs depende dele para
// posicionar o indicador da aba ativa. Stub no-op: o teste não mede layout.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

// Testing Library não desmonta sozinha quando `globals` está ligado em alguns
// setups; desmontar explicitamente evita que o DOM de um teste vaze no outro.
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
})
