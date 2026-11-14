import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': 'http://127.0.0.1:8066', '/ws': { target: 'ws://127.0.0.1:8066', ws: true } } },
  build: { rollupOptions: { output: { manualChunks: { charts: ['echarts'], vue: ['vue'] } } } }
})
