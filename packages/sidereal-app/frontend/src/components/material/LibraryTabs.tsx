import { NavLink } from "react-router-dom";

import { cx } from "@/lib/cx";

import styles from "./material.module.css";

const TABS = [
  { to: "/library", label: "Material", end: true },
  { to: "/library/papers", label: "Papers", end: false },
];

/** The two halves of the library. Each is its own route, so either can be linked to. */
export function LibraryTabs() {
  return (
    <nav className={styles.libraryTabs} aria-label="Library">
      {TABS.map(({ to, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => cx(styles.libraryTab, isActive && styles.libraryTabActive)}
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
