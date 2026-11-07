import { splitTurnRefs } from '../../lib/turnRefs'

// Текст, в котором ссылки #N ведут к реплике диалога
export default function TurnRefText({ text, turnCount, onTurn }) {
  return splitTurnRefs(text, turnCount).map((part, index) =>
    part.turn ? (
      <button
        key={index}
        type="button"
        onClick={() => onTurn(part.turn)}
        className="font-medium text-brand-text underline decoration-dotted underline-offset-2"
      >
        {part.text}
      </button>
    ) : (
      <span key={index}>{part.text}</span>
    ),
  )
}
