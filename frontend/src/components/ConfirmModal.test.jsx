import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ConfirmModal from './ConfirmModal'

function montar(props = {}) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(<ConfirmModal onConfirm={onConfirm} onCancel={onCancel} {...props} />)
  return { onConfirm, onCancel }
}

describe('ConfirmModal', () => {
  it('mostra título e mensagem', () => {
    montar({ title: 'Excluir projeto', message: 'Some para sempre.' })
    expect(screen.getByText('Excluir projeto')).toBeInTheDocument()
    expect(screen.getByText('Some para sempre.')).toBeInTheDocument()
  })

  it('confirma e cancela pelos botões', async () => {
    const { onConfirm, onCancel } = montar({ confirmLabel: 'Excluir', cancelLabel: 'Voltar' })
    await userEvent.click(screen.getByRole('button', { name: 'Excluir' }))
    expect(onConfirm).toHaveBeenCalledOnce()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('Escape cancela', async () => {
    const { onCancel } = montar()
    await userEvent.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('durante o loading ignora teclado e desabilita os botões', async () => {
    const { onConfirm, onCancel } = montar({ loading: true })
    await userEvent.keyboard('{Escape}')
    await userEvent.keyboard('{Enter}')
    expect(onConfirm).not.toHaveBeenCalled()
    expect(onCancel).not.toHaveBeenCalled()
    for (const botao of screen.getAllByRole('button')) {
      expect(botao).toBeDisabled()
    }
  })

  it('restaura o scroll do body ao desmontar', () => {
    const { unmount } = render(<ConfirmModal onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(document.body.style.overflow).toBe('hidden')
    unmount()
    expect(document.body.style.overflow).toBe('')
  })
})
