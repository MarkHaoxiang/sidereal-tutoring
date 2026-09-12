import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Wordmark } from "@/components/Wordmark";
import { Button } from "@/components/ui";
import { useAuth, userDisplayName } from "@/lib/auth-context";
import { cx } from "@/lib/cx";

import styles from "./StudentNav.module.css";

const LINKS = [
  { to: "/me", label: "Home", end: true },
  { to: "/me/homework", label: "Homework", end: false },
  { to: "/me/feedback", label: "Feedback", end: false },
  { to: "/me/plan", label: "Plan", end: false },
  { to: "/me/sessions", label: "Lessons", end: false },
];

export function StudentNav() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
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
    <header className={styles.nav}>
      <div className={styles.inner}>
        <Link to="/me" className={styles.brand} aria-label="Sidereal Tutoring — home">
          <Wordmark size="sm" />
        </Link>

        <button
          type="button"
          className={styles.menuButton}
          aria-label={menuOpen ? "Close the menu" : "Open the menu"}
          aria-expanded={menuOpen}
          onClick={() => {
            setMenuOpen((open) => !open);
          }}
        >
          {menuOpen ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
        </button>

        <nav className={cx(styles.menu, menuOpen && styles.menuOpen)} aria-label="Main">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => cx(styles.link, isActive && styles.linkActive)}
              onClick={() => {
                setMenuOpen(false);
              }}
            >
              {link.label}
            </NavLink>
          ))}
          <span className={styles.spacer} />
          <span className={styles.account}>
            <Link
              to="/me/account"
              className={styles.user}
              onClick={() => {
                setMenuOpen(false);
              }}
            >
              {userDisplayName(user)}
            </Link>
            <ThemeToggle />
            <Button
              variant="ghost"
              size="sm"
              loading={signingOut}
              onClick={() => {
                void signOut();
              }}
            >
              Sign out
            </Button>
          </span>
        </nav>
      </div>
    </header>
  );
}
