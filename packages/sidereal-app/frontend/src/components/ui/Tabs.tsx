import { useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { cx } from "@/lib/cx";

import styles from "./Tabs.module.css";

export interface TabItem {
  /** Absolute path of the tab's nested route. */
  to: string;
  label: string;
}

export interface TabsProps {
  label: string;
  items: TabItem[];
  /** Id of the <TabPanel> the tabs control. */
  panelId: string;
}

// Tabs are nested routes, not local state: each tab is its own route under the parent
// page, so a tab is linkable, survives a reload, and the back button moves between
// tabs. The selected tab is the one whose `to` prefixes the current path; the panel
// the tabs control is the parent's <Outlet />, wrapped in <TabPanel>.
export function Tabs({ label, items, panelId }: TabsProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const tabRefs = useRef<(HTMLAnchorElement | null)[]>([]);

  const isSelected = (to: string) => pathname === to || pathname.startsWith(`${to}/`);
  const selectedIndex = Math.max(
    items.findIndex((item) => isSelected(item.to)),
    0
  );

  const handleKeyDown = (event: KeyboardEvent<HTMLAnchorElement>) => {
    const lastIndex = items.length - 1;
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = selectedIndex === lastIndex ? 0 : selectedIndex + 1;
    } else if (event.key === "ArrowLeft") {
      nextIndex = selectedIndex === 0 ? lastIndex : selectedIndex - 1;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = lastIndex;
    }
    const next = nextIndex === null ? undefined : items[nextIndex];
    if (!next || nextIndex === null) {
      return;
    }
    event.preventDefault();
    tabRefs.current[nextIndex]?.focus();
    void navigate(next.to);
  };

  return (
    <div className={styles.tablist} role="tablist" aria-label={label}>
      {items.map((item, index) => {
        const selected = index === selectedIndex;
        return (
          <Link
            key={item.to}
            to={item.to}
            role="tab"
            id={`${panelId}-tab-${String(index)}`}
            aria-controls={panelId}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            className={cx(styles.tab, selected && styles.selected)}
            ref={(element) => {
              tabRefs.current[index] = element;
            }}
            onKeyDown={handleKeyDown}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}

export function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  return (
    <div id={id} role="tabpanel" className={styles.panel}>
      {children}
    </div>
  );
}
