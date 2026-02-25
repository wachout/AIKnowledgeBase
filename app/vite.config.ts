import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import sourceIdentifierPlugin from 'vite-plugin-source-identifier'

const isProd = process.env.BUILD_MODE === 'prod'
export default defineConfig({
  plugins: [
    react(), 
    sourceIdentifierPlugin({
      enabled: !isProd,
      attributePrefix: 'data-matrix',
      includeProps: true,
    })
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: '0.0.0.0', // 监听所有网络接口，支持通过IP地址访问
    port: 5173, // 默认端口
    strictPort: false, // 如果端口被占用，自动使用下一个可用端口
  },
  preview: {
    host: '0.0.0.0', // 生产环境预览也支持IP访问
    port: 4173,
  }
})

