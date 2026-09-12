import { House, ListTree, LogOut, Shield, Users } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { callerRole, useAuth, userDisplayName } from "@/lib/auth-context";
import { cx } from "@/lib/cx";

import { ThemeToggle } from "./ThemeToggle";
import { Wordmark } from "./Wordmark";
import styles from "./Sidebar.module.css";

const LINKS = [
  { to: "/", label: "Home", end: true, Icon: House },
  { to: "/students", label: "Students", end: false, Icon: Users },
  { to: "/topics", label: "Topics", end: false, Icon: ListTree },
];

// An admin is at home here too; this is their way back to the surface that is only theirs.
const ADMIN_LINK = { to: "/admin", label: "Admin", end: false, Icon: Shield };

export function Sidebar() {
  const { user, me, logout } = useAuth();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  const signOut = async () => {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
      void navigate("/login", { replace: true });
    }
  };

  return (
    <div className={styles.sidebar}>
      <Link to="/" className={styles.brand} aria-label="Sidereal Tutoring — home">
        <Wordmark size="sm" />
      </Link>

      <nav className={styles.nav} aria-label="Main">
        {(callerRole(me) === "admin" ? [...LINKS, ADMIN_LINK] : LINKS).map(({ to, label, end, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => cx(styles.link, isActive && styles.linkActive)}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className={styles.footer}>
        <Link to="/account" className={styles.user}>
          <span className={styles.userEyebrow}>Signed in as</span>
          <span className={styles.userName}>{userDisplayName(user)}</span>
        </Link>
        <div className={styles.footerActions}>
          <ThemeToggle />
          <button
            type="button"
            className={styles.signOut}
            disabled={signingOut}
            onClick={() => {
              void signOut();
            }}
          >
            <LogOut size={15} aria-hidden="true" />
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </div>
    </div>
  );
}
