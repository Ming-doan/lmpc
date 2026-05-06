import { useState } from 'react'

interface Props {
  onAuth: (token: string) => void
}

export function AuthModal({ onAuth }: Props) {
  const [value, setValue] = useState('')
  const [error, setError] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!value.trim()) {
      setError('Token is required')
      return
    }
    onAuth(value.trim())
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-secondary/50 backdrop-blur-md">
      <div className="w-[360px] rounded bg-white p-8 shadow-2xl">
        <h2 className="mb-1 font-serif text-xl font-bold text-secondary">Admin access required</h2>
        <p className="mb-5 text-sm text-gray-500">
          Enter your <code className="font-mono text-xs">APP_TOKEN</code> to continue. It will be saved in your browser.
        </p>
        <form onSubmit={submit} className="space-y-3">
          <input
            className="input"
            type="password"
            placeholder="APP_TOKEN"
            value={value}
            onChange={e => { setValue(e.target.value); setError('') }}
            autoFocus
          />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button type="submit" className="btn w-full justify-center">
            Authenticate →
          </button>
        </form>
      </div>
    </div>
  )
}
