// Placeholder screens proving the routed shell. Each is built out in a later
// commit of the frontend phase (see docs/implementation-plans/
// phase-loop-mvp-frontend.md): F-F approval gate, F-G the steady-state read
// views. (Onboarding F-C, generation F-D, schedule review F-E — own modules.)

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

export const ApprovalScreen = () => <Placeholder title="Approve & write to calendar" commit="F-F" />
export const TodayScreen = () => <Placeholder title="Today" commit="F-G" />
export const AccountabilityScreen = () => <Placeholder title="Accountability" commit="F-G" />
export const ThresholdsScreen = () => <Placeholder title="Thresholds" commit="F-G" />
