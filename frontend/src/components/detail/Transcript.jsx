import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardHeader } from '../ui/Card'
import TurnMessage from './TurnMessage'

export default function Transcript({ turns, evidence, focus, onPlay, player }) {
  const { t } = useTranslation()
  const listRef = useRef(null)

  useEffect(() => {
    if (!focus) return
    listRef.current?.querySelector(`[data-turn="${focus.turn}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [focus])

  return (
    <Card className="flex max-h-[70vh] flex-col lg:sticky lg:top-20 lg:max-h-[calc(100vh-6.5rem)]">
      <CardHeader title={t('detail.transcript')} hint={t('detail.turnCount', { count: turns.length })} />
      {player}
      <div ref={listRef} className="space-y-2 overflow-y-auto p-5 pt-2">
        {turns.map((turn) => {
          const isFocused = focus?.turn === turn.index
          return (
            <TurnMessage
              key={isFocused ? `${turn.index}-${focus.nonce}` : turn.index}
              turn={turn}
              highlighted={evidence.has(turn.index)}
              flash={isFocused}
              onPlay={onPlay && (() => onPlay(turn.index))}
            />
          )
        })}
      </div>
    </Card>
  )
}
