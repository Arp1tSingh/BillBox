import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '../auth/AuthProvider'
import { api, ApiError } from '../lib/api'
import type { Household } from '../lib/types'

export const householdKey = (userId: string | undefined) => ['household', userId ?? 'anon'] as const

export function useHousehold() {
  const { user } = useAuth()
  return useQuery<Household, ApiError>({
    queryKey: householdKey(user?.id),
    queryFn: () => api.get<Household>('/households/me'),
    enabled: Boolean(user),
    staleTime: 15_000,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 1,
  })
}

export function useCreateHousehold() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation<Household, ApiError, string>({
    mutationFn: (name) => api.post<Household>('/households', { name }),
    onSuccess: (household) => {
      queryClient.setQueryData(householdKey(user?.id), household)
    },
  })
}

export function useJoinHousehold() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation<Household, ApiError, string>({
    mutationFn: (inviteCode) => api.post<Household>('/households/join', { invite_code: inviteCode }),
    onSuccess: (household) => {
      queryClient.setQueryData(householdKey(user?.id), household)
    },
  })
}

export function useRotateInvite() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  return useMutation<Household, ApiError, void>({
    mutationFn: () => api.post<Household>('/households/rotate-invite'),
    onSuccess: (household) => {
      queryClient.setQueryData(householdKey(user?.id), household)
    },
  })
}
