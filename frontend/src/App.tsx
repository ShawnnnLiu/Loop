import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { ApiError, api } from './api/client'
import type { MeResult } from './api/types'
import { Topbar } from './components/Topbar'
import {
  AccountabilityScreen,
  GenerationScreen,
  OnboardingScreen,
  ScheduleReviewScreen,
  ThresholdsScreen,
  TodayScreen,
} from './screens/placeholders'

type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; me: MeResult }
  | { status: 'error'; message: string }

export function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let active = true
    api
      .me()
      .then((me) => {
        if (active) setState({ status: 'ready', me })
      })
      .catch((error: unknown) => {
        // A 401 has already redirected to /auth/login — leave the screen as-is.
        if (error instanceof ApiError && error.status === 401) return
        if (active) {
          const message = error instanceof Error ? error.message : 'failed to load'
          setState({ status: 'error', message })
        }
      })
    return () => {
      active = false
    }
  }, [])

  if (state.status === 'loading') {
    return <div className="screen-center muted">Loading…</div>
  }
  if (state.status === 'error') {
    return <div className="screen-center">Couldn’t reach Loop — {state.message}</div>
  }

  const { me } = state
  return (
    <div className="app-shell">
      <Topbar email={me.email} />
      <main className="app-main">
        <Routes>
          {/* A connected user with no profile lands in onboarding; otherwise Today. */}
          <Route path="/" element={<Navigate to={me.onboarded ? '/today' : '/onboarding'} replace />} />
          <Route path="/onboarding" element={<OnboardingScreen />} />
          <Route path="/plan" element={<GenerationScreen />} />
          <Route path="/review" element={<ScheduleReviewScreen />} />
          <Route path="/today" element={<TodayScreen />} />
          <Route path="/accountability" element={<AccountabilityScreen />} />
          <Route path="/thresholds" element={<ThresholdsScreen />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
