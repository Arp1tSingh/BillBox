import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '../auth/AuthProvider'
import { api, ApiError } from '../lib/api'
import type {
  ReceiptDetail,
  ReceiptSearchResponse,
  ReceiptUpdateInput,
  TagView,
} from '../lib/types'

export const receiptsKey = (userId: string | undefined) =>
  ['receipts', userId ?? 'anon'] as const
export const receiptKey = (id: string) => ['receipt', id] as const
export const tagsKey = (userId: string | undefined) =>
  ['tags', userId ?? 'anon'] as const

export interface ReceiptSearchParams {
  q?: string
  tag?: string[]
  from?: string
  to?: string
  min?: string
  max?: string
  sort?: string
  page?: number
  page_size?: number
}

function buildQuery(params: ReceiptSearchParams): string {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  for (const tag of params.tag ?? []) query.append('tag', tag)
  for (const key of ['from', 'to', 'min', 'max', 'sort'] as const) {
    const value = params[key]
    if (value) query.set(key, value)
  }
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  return query.toString()
}

export function useReceipts(params: ReceiptSearchParams = {}) {
  const { user } = useAuth()
  return useQuery<ReceiptSearchResponse, ApiError>({
    queryKey: [...receiptsKey(user?.id), params],
    queryFn: () => {
      const query = buildQuery(params)
      return api.get<ReceiptSearchResponse>(`/receipts${query ? `?${query}` : ''}`)
    },
    enabled: Boolean(user),
    staleTime: 10_000,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 1,
  })
}

export function useTags() {
  const { user } = useAuth()
  return useQuery<TagView[], ApiError>({
    queryKey: tagsKey(user?.id),
    queryFn: () => api.get<TagView[]>('/tags'),
    enabled: Boolean(user),
    staleTime: 30_000,
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
      void queryClient.invalidateQueries({ queryKey: ['tags'] })
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
      void queryClient.invalidateQueries({ queryKey: ['tags'] })
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
      void queryClient.invalidateQueries({ queryKey: ['tags'] })
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
      void queryClient.invalidateQueries({ queryKey: ['tags'] })
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
      void queryClient.invalidateQueries({ queryKey: ['tags'] })
    },
  })
}
