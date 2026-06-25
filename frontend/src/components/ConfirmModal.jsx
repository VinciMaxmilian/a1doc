import { useEffect } from 'react'

export default function ConfirmModal({
  title = 'Confirmar exclusão',
  message = 'Esta ação não pode ser desfeita.',
  confirmLabel = 'Excluir',
  cancelLabel = 'Cancelar',
  danger = true,
  loading = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape' && !loading) onCancel()
      if (e.key === 'Enter' && !loading) onConfirm()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onConfirm, onCancel, loading])

  return (
    <div
      className="modal-overlay"
      onClick={e => !loading && e.target === e.currentTarget && onCancel()}
    >
      <div className="modal confirm-modal">
        <button
          className="modal-close"
          style={{ position: 'absolute', top: 16, right: 16 }}
          onClick={onCancel}
          disabled={loading}
        >✕</button>

        <div className="confirm-modal-icon">
          {danger ? '🗑️' : '⚠️'}
        </div>

        <h3 className="confirm-modal-title">{title}</h3>
        <p className="confirm-modal-msg">{message}</p>

        <div className="confirm-modal-actions">
          <button
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={loading}
            style={{ minWidth: 110 }}
          >
            {cancelLabel}
          </button>
          <button
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}${loading ? ' btn-loading' : ''}`}
            onClick={onConfirm}
            disabled={loading}
            style={{ minWidth: 110 }}
          >
            {!loading && confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
