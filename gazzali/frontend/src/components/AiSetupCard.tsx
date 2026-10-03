import { SystemHealth } from '../api'

/** Which AI models the platform is actually using, from /system/health. */
export function AiSetupCard({ health }: { health?: SystemHealth }) {
  const ai = health?.ai
  const rows: [string, string, string | undefined, boolean | undefined][] = [
    ['Background AI jobs', 'Drafts, hypotheses, reviews', ai?.runner_model, ai?.runner_configured],
    ['Assistant', 'AI copilot, grant writer, figures', ai ? `${ai.assistant_model}${ai.assistant_provider ? ` (${ai.assistant_provider})` : ''}` : undefined, undefined],
  ]
  return (
    <div className="card" style={{ marginBottom: 8, display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map(([title, sub, model, ok]) => (
        <div key={title} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-heading)' }}>{title}</div>
            <div style={{ fontSize: 13, color: 'var(--text-3)' }}>{sub}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <code style={{ fontSize: 13 }}>{model ?? '—'}</code>
            {ok !== undefined && (
              <div style={{ fontSize: 12, fontWeight: 600, color: ok ? 'var(--emerald)' : 'var(--rose)' }}>
                {ok ? 'API key configured' : 'API key missing'}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
