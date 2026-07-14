import { useQuery } from '@tanstack/react-query'

import { getSRConfigRecord } from '@/sr'
import { queryClient, writeCache } from '@/lib/query-client'
import type { SRConfigRecord } from '@/types/sr'

// One shared cache for the whole profile config record (`GET /api/config`).
// Every settings surface (MCP, model, config) reads and writes through this key
// so a save in one shows in the others, and revisiting a tab paints the cache
// instead of blanking on a fresh fetch.
//
// Distinct from session/hooks/use-sr-config.ts, which is side-effecting —
// it pushes personality/cwd/voice/… into the session stores for live chat.
export const SR_CONFIG_KEY = ['sr-config-record'] as const

// staleTime 0 → serve cache instantly, background-revalidate on every mount.
export const useSRConfigRecord = () =>
  useQuery({ queryKey: SR_CONFIG_KEY, queryFn: getSRConfigRecord, staleTime: 0 })

export const setSRConfigCache = writeCache<SRConfigRecord>(SR_CONFIG_KEY)

export const invalidateSRConfig = () => queryClient.invalidateQueries({ queryKey: SR_CONFIG_KEY })
