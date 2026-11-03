import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import { UploadQueueProvider } from './components/UploadQueueProvider'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <UploadQueueProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </UploadQueueProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
