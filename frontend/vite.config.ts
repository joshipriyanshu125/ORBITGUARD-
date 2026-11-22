import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import cesium from 'vite-plugin-cesium'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    cesium()
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'https://orbitguard-exb5.onrender.com',
        changeOrigin: true,
        secure: true
      }
    }
  }
})
