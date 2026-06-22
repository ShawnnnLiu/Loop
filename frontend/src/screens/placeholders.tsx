// Placeholder screens proving the routed shell. Each is built out in a later
// commit of the frontend phase (see docs/implementation-plans/
// phase-loop-mvp-frontend.md): F-E drag-adjust, F-G the steady-state read
// views. (Onboarding shipped in F-C, generation in F-D — see their modules.)

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

export const ScheduleReviewScreen = () => <Placeholder title="Review your week" commit="F-E" />
export const TodayScreen = () => <Placeholder title="Today" commit="F-G" />
export const AccountabilityScreen = () => <Placeholder title="Accountability" commit="F-G" />
export const ThresholdsScreen = () => <Placeholder title="Thresholds" commit="F-G" />
