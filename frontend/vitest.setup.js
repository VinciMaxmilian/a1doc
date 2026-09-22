import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Testing Library não desmonta sozinha quando `globals` está ligado em alguns
// setups; desmontar explicitamente evita que o DOM de um teste vaze no outro.
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
})
