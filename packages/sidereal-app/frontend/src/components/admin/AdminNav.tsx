import { Database, Gauge, House, ListTree, LogOut, Menu, Sparkles, Users, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Wordmark } from "@/components/Wordmark";
import { useAuth, userDisplayName } from "@/lib/auth-context";
import { cx } from "@/lib/cx";
import { directusUrl } from "@/lib/directus";

import styles from "./AdminNav.module.css";

const LINKS = [
  { to: "/admin", label: "Dashboard", end: true, Icon: Gauge },
  { to: "/admin/tutors", label: "Tutors", end: false, Icon: Users },
  { to: "/admin/jobs", label: "Jobs", end: false, Icon: Sparkles },
  { to: "/admin/topics", label: "Topics", end: false, Icon: ListTree },
];

const DATA_MODEL_URL = `${directusUrl}/admin/settings/data-model`;

/**
 * One navigation, two skins: a column beside the page above 64rem, a bar with a menu
 * above it below that. The shell picks, so only one of them is ever in the document.
 */
export function AdminNav({ variant }: { variant: "sidebar" | "top" }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const top = variant === "top";

  const signOut = async () => {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
      void navigate("/login", { replace: true });
    }
  };

  const close = () => {
    setMenuOpen(false);
  };

  return (
    <div className={cx(styles.nav, top ? styles.top : styles.sidebar)}>
      <div className={styles.head}>
        <Link to="/admin" className={styles.brand} aria-label="Sidereal Tutoring — admin">
          <Wordmark size="sm" />
          <span className={styles.badge}>Admin</span>
        </Link>
        {top ? (
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
        ) : null}
      </div>

      <div className={cx(styles.body, top && !menuOpen && styles.bodyClosed)}>
        <nav className={styles.links} aria-label="Main">
          {LINKS.map(({ to, label, end, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => cx(styles.link, isActive && styles.linkActive)}
              onClick={close}
            >
              <Icon size={16} aria-hidden="true" />
              {label}
            </NavLink>
          ))}

          <span className={styles.divider} aria-hidden="true" />

          <Link to="/" className={styles.link} onClick={close}>
            <House size={16} aria-hidden="true" />
            Tutor app
          </Link>
          <a
            href={DATA_MODEL_URL}
            target="_blank"
            rel="noreferrer"
            className={styles.link}
            onClick={close}
          >
            <Database size={16} aria-hidden="true" />
            Directus (separate sign-in)
          </a>
        </nav>

        <div className={styles.footer}>
          <Link to="/account" className={styles.user} onClick={close}>
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
    </div>
  );
}
