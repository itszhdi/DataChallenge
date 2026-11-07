import clsx from 'clsx'
import { useTranslation } from 'react-i18next'
import { LuPlay } from 'react-icons/lu'
import { formatClock } from '../../lib/format'

const SPEAKER_STYLE = {
  operator: 'border-brand/40 bg-brand-soft',
  client: 'border-line bg-surface',
  bot: 'border-transparent bg-surface-muted italic text-ink-muted',
  system: 'border-dashed border-line text-ink-muted',
}

export default function TurnMessage({ turn, highlighted, flash, onPlay }) {
  const { t } = useTranslation()
  return (
    <div
      data-turn={turn.index}
      className={clsx(
        'rounded-xl border p-3 text-sm',
        SPEAKER_STYLE[turn.speaker] ?? SPEAKER_STYLE.system,
        highlighted && 'ring-1 ring-warn',
        flash && 'turn-flash',
      )}
    >
      <div className="mb-1 flex items-center gap-2 text-xs not-italic">
        <b>
          {t(`speaker.${turn.speaker}`, { defaultValue: turn.speaker })}
          {turn.speaker === 'unknown' && turn.speaker_raw && ` (${turn.speaker_raw})`}
        </b>
        <span className="text-ink-muted tabular-nums" title={turn.timestamp}>
          #{turn.index} · {formatClock(turn.offset_sec)}
        </span>
        {turn.pre_recording && <span className="text-ink-muted">· {t('detail.preRecording')}</span>}
        {onPlay && (
          <button type="button" onClick={onPlay} aria-label={t('detail.playTurn', { turn: turn.index })} className="ml-auto text-ink-muted hover:text-brand-text">
            <LuPlay className="size-4" />
          </button>
        )}
      </div>
      <p className={clsx('break-words whitespace-pre-wrap', turn.empty && 'text-ink-muted')}>{turn.empty || !turn.text ? t('detail.emptyTurn') : turn.text}</p>
    </div>
  )
}
