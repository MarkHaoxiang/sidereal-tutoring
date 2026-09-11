import { GraduationCap, LogOut } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "@/lib/auth-context";

import { ThemeToggle } from "./ThemeToggle";
import styles from "./TopNav.module.css";

export function TopNav() {
  const { logout } = useAuth();

  return (
    <header className={styles.nav}>
      <Link to="/" className={styles.brand}>
        <GraduationCap size={20} aria-hidden="true" />
        Sidereal Tutoring
      </Link>
      <div className={styles.actions}>
        <ThemeToggle />
        <button
          type="button"
          className={styles.logout}
          onClick={() => {
            void logout();
          }}
        >
          <LogOut size={16} aria-hidden="true" />
          Log out
        </button>
      </div>
    </header>
  );
}
