import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import favicon from './assets/favicon.png'
import './i18n'
import './index.css'

// фавикон через импорт — в однофайловой сборке он встраивается как data-URL
document.querySelector('link[rel="icon"]').href = favicon

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
