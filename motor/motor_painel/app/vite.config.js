import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  /* UMA copia do three, sempre.
     O `3d-force-graph` declara `three: '>=0.118 <1'` e resolve para a mais nova,
     enquanto um `three` fixado no topo fica noutra versao. Duas copias
     coexistem sem conflito de instalacao, o build passa, os testes passam -- e
     a tela abre PRETA, porque um `Mesh` de uma copia entra no renderer da
     outra e estoura no laco de animacao (`matrixWorld.determinantAffine is not
     a function`). Falha que so aparece olhando. */
  resolve: { dedupe: ['three'] },
  server: {
    proxy: {
      '/dados': {
        target: 'http://localhost:8378',
        changeOrigin: true,
      },
    },
  },
})