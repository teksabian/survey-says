import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/static/react/',
  build: {
    outDir: '../static/react',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/main.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
  server: {
    proxy: {
      '/play': 'http://localhost:5000',
      '/api': 'http://localhost:5000',
      '/join': 'http://localhost:5000',
      '/static': 'http://localhost:5000',
      '/socket.io': {
        target: 'http://localhost:5000',
        ws: true,
      },
    },
  },
})
