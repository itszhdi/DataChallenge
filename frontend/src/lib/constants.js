export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

export const CHANNEL = { CHAT: 'agent chat', CALL: 'voice call' }
export const LANGUAGES = ['RU', 'KZ', 'EN']
export const CHANNELS = [CHANNEL.CHAT, CHANNEL.CALL]
export const CHANNEL_LABEL_KEYS = { [CHANNEL.CHAT]: 'channel.chat', [CHANNEL.CALL]: 'channel.call' }
export const DISTRIBUTION_BUCKETS = ['critical', 'risk', 'norm', 'reference']

// Пороги цвета для процента выполнения и итога
export const SCORE_GOOD_FROM = 80
export const SCORE_WARN_FROM = 60

export const PAGE_SIZE = 10
export const JOB_POLL_MS = 2500

// Метка реплики в звонке — момент распознавания: сама фраза звучит примерно на 3 секунды раньше
export const AUDIO_LEAD_SEC = -3

export const STORAGE_KEYS = {
  theme: 'cqa-theme',
  language: 'cqa-language',
  dataset: 'cqa-dataset',
  exportMeta: 'cqa-export-meta',
  jobId: 'cqa-job-id',
  jobAcknowledged: 'cqa-job-acknowledged',
  sidebar: 'cqa-sidebar-open',
}
