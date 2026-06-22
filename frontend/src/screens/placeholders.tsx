// Placeholder screens proving the routed shell. Each is built out in a later
// commit of the frontend phase (see docs/implementation-plans/
// phase-loop-mvp-frontend.md): F-C onboarding, F-D generation, F-E drag-adjust,
// F-G the steady-state read views.

function Placeholder({ title, commit }: { title: string; commit: string }) {
  return (
    <section className="screen">
      <span className="label">Loop</span>
      <h1 className="t-h1" style={{ marginTop: 8 }}>
        {title}
      </h1>
      <p className="muted" style={{ marginTop: 6 }}>
        Coming in {commit}.
      </p>
    </section>
  )
}

export const OnboardingScreen = () => <Placeholder title="Set up your plan" commit="F-C" />
export const GenerationScreen = () => <Placeholder title="Building your plan" commit="F-D" />
export const ScheduleReviewScreen = () => <Placeholder title="Review your week" commit="F-E" />
export const TodayScreen = () => <Placeholder title="Today" commit="F-G" />
export const AccountabilityScreen = () => <Placeholder title="Accountability" commit="F-G" />
export const ThresholdsScreen = () => <Placeholder title="Thresholds" commit="F-G" />
