import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// base './' — сборка открывается из любого пути, в том числе как веб-ресурс Dynamics 365
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
})
