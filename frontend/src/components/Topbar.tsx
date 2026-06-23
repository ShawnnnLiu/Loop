import { Link, NavLink } from 'react-router-dom'

import { logout } from '../auth/session'

const NAV = [
  { to: '/today', label: 'Today' },
  { to: '/review', label: 'Week' },
  { to: '/plan', label: 'Plan' },
  { to: '/accountability', label: 'Progress' },
  { to: '/thresholds', label: 'Tuning' },
] as const

export function Topbar({ email }: { email: string | null }) {
  return (
    <header className="tb">
      <Link to="/app" className="brand" style={{ textDecoration: 'none', color: 'inherit' }}>
        <span className="glyph">L</span>
        <span className="word">Loop</span>
      </Link>
      <nav className="tb-nav">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'on' : '')}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <span className="spacer" />
      {email && (
        <span className="muted" style={{ fontSize: 13 }}>
          {email}
        </span>
      )}
      <button className="btn btn-soft sm" onClick={() => void logout()}>
        Log out
      </button>
    </header>
  )
}
