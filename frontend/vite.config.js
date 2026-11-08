import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// base './' — сборка открывается из любого пути, в том числе как веб-ресурс Dynamics 365
// --mode single — всё (JS, CSS, шрифты, картинки) в один build/index.html, открывается двойным кликом
export default defineConfig(({ mode }) => {
  const single = mode === 'single'
  return {
    base: './',
    plugins: [react(), tailwindcss(), ...(single ? [viteSingleFile()] : [])],
    ...(single && {
      build: {
        outDir: 'build',
        emptyOutDir: true,
        assetsInlineLimit: Number.MAX_SAFE_INTEGER,
      },
    }),
  }
})
