import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: 'apps/desktop',
  clearScreen: false,
  server: {
    port: 1420, strictPort: true, host: '127.0.0.1',
    watch: { ignored: ['**/src-tauri/**'] },
  },
  build: { outDir: '../../dist', emptyOutDir: true, target: 'es2022' },
});
