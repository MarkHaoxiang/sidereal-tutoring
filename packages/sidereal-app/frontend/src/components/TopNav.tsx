import { GraduationCap, Menu, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui";
import { useAuth, userDisplayName } from "@/lib/auth-context";
import { cx } from "@/lib/cx";

import { ThemeToggle } from "./ThemeToggle";
import styles from "./TopNav.module.css";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/students", label: "Students", end: false },
];

export function TopNav() {
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
        <Link to="/" className={styles.brand}>
          <GraduationCap size={20} aria-hidden="true" />
          Sidereal Tutoring
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
          <span className={styles.user}>{userDisplayName(user)}</span>
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
        </nav>
      </div>
    </header>
  );
}
