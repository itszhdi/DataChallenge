import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export default function AudioPlayer({ ref, src, sourceUrl }) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)
  return (
    <div className="px-5 pb-2">
      <audio ref={ref} src={src} controls preload="metadata" className="w-full" onError={() => setFailed(true)} />
      {failed && (
        <p className="mt-1 text-xs text-danger-text">
          {t('detail.audioFailed')}{' '}
          <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="underline">
            {t('detail.audioOpen')}
          </a>
        </p>
      )}
    </div>
  )
}
