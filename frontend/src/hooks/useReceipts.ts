import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '../auth/AuthProvider'
import { api, ApiError } from '../lib/api'
import type {
  ReceiptDetail,
  ReceiptSummary,
  ReceiptUpdateInput,
} from '../lib/types'

export const receiptsKey = (userId: string | undefined) =>
  ['receipts', userId ?? 'anon'] as const
export const receiptKey = (id: string) => ['receipt', id] as const

export function useReceipts() {
  const { user } = useAuth()
  return useQuery<ReceiptSummary[], ApiError>({
    queryKey: receiptsKey(user?.id),
    queryFn: () => api.get<ReceiptSummary[]>('/receipts?limit=20'),
    enabled: Boolean(user),
    staleTime: 10_000,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 1,
  })
}

export function useReceipt(id: string | undefined) {
  const { user } = useAuth()
  return useQuery<ReceiptDetail, ApiError>({
    queryKey: receiptKey(id ?? 'missing'),
    queryFn: () => api.get<ReceiptDetail>(`/receipts/${id}`),
    enabled: Boolean(user && id),
    refetchInterval: (query) =>
      query.state.data?.status === 'processing' ? 2_000 : false,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 1,
  })
}

export function useProcessReceipt(id: string) {
  const queryClient = useQueryClient()
  return useMutation<ReceiptDetail, ApiError, void>({
    mutationFn: () => api.post<ReceiptDetail>(`/receipts/${id}/process`),
    onSuccess: (detail) => {
      queryClient.setQueryData(receiptKey(id), detail)
      void queryClient.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}

export function useUpdateReceipt(id: string) {
  const queryClient = useQueryClient()
  return useMutation<ReceiptDetail, ApiError, ReceiptUpdateInput>({
    mutationFn: (fields) => api.patch<ReceiptDetail>(`/receipts/${id}`, fields),
    onSuccess: (detail) => {
      queryClient.setQueryData(receiptKey(id), detail)
      void queryClient.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}

export function useDeleteReceipt(id: string) {
  const queryClient = useQueryClient()
  return useMutation<void, ApiError, void>({
    mutationFn: () => api.delete<void>(`/receipts/${id}`),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: receiptKey(id) })
      void queryClient.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}

export function useAddReceiptTag(id: string) {
  const queryClient = useQueryClient()
  return useMutation<ReceiptDetail, ApiError, { tag_id?: string; label?: string }>({
    mutationFn: (payload) => api.post<ReceiptDetail>(`/receipts/${id}/tags`, payload),
    onSuccess: (detail) => {
      queryClient.setQueryData(receiptKey(id), detail)
      void queryClient.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}

export function useRemoveReceiptTag(id: string) {
  const queryClient = useQueryClient()
  return useMutation<ReceiptDetail, ApiError, string>({
    mutationFn: (tagId) =>
      api.delete<ReceiptDetail>(`/receipts/${id}/tags/${tagId}`),
    onSuccess: (detail) => {
      queryClient.setQueryData(receiptKey(id), detail)
      void queryClient.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}
