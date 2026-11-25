import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'
import nextTs from 'eslint-config-next/typescript'

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores(['.next/**', 'node_modules/**', 'next-env.d.ts', 'components/ui/**', 'hooks/use-toast.ts']),
  {
    files: ['app/progress/page.tsx', 'app/search/page.tsx'],
    rules: { 'react-hooks/set-state-in-effect': 'off' },
  },
])
