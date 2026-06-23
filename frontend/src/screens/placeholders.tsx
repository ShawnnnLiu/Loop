// Placeholder screens proving the routed shell. Built out in F-G (the
// steady-state read views). The approval gate (F-F) is now a real module
// (screens/Approval.tsx); onboarding (F-C), generation (F-D), and schedule
// review (F-E) are their own modules too.

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

export const TodayScreen = () => <Placeholder title="Today" commit="F-G" />
export const AccountabilityScreen = () => <Placeholder title="Accountability" commit="F-G" />
export const ThresholdsScreen = () => <Placeholder title="Thresholds" commit="F-G" />
