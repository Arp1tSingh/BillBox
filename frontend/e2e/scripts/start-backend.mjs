import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import dotenv from 'dotenv'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(here, '../..')
const repoRoot = path.resolve(frontendDir, '..')
const backendDir = path.join(repoRoot, 'backend')

dotenv.config({ path: path.join(repoRoot, '.env.e2e') })
dotenv.config({ path: path.join(repoRoot, '.env.e2e.local'), override: true })

const apiUrl = new URL(process.env.API_BASE_URL ?? 'http://127.0.0.1:8000')
const host = apiUrl.hostname || '127.0.0.1'
const port = apiUrl.port || '8000'

const candidates =
  process.platform === 'win32'
    ? [path.join(backendDir, '.venv', 'Scripts', 'python.exe')]
    : [path.join(backendDir, '.venv', 'bin', 'python')]
const python =
  process.env.BACKEND_PYTHON ||
  candidates.find((candidate) => existsSync(candidate)) ||
  (process.platform === 'win32' ? 'python' : 'python3')

console.log(`Starting BillBox API with ${python} on ${host}:${port}`)

const child = spawn(
  python,
  ['-m', 'uvicorn', 'app.main:app', '--host', host, '--port', port],
  {
    cwd: backendDir,
    env: {
      ...process.env,
      ENVIRONMENT: process.env.ENVIRONMENT ?? 'test',
      GEMINI_MOCK: process.env.GEMINI_MOCK ?? '1',
    },
    stdio: 'inherit',
  },
)

child.on('error', (error) => {
  console.error('Could not start the API:', error)
  process.exit(1)
})

child.on('exit', (code) => {
  process.exit(code ?? 1)
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal))
}
