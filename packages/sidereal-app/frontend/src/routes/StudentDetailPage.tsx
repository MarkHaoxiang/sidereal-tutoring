import { readItem } from "@directus/sdk";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { directus } from "@/lib/directus";

import styles from "./StudentDetailPage.module.css";
import { DocumentsTab } from "./student-tabs/DocumentsTab";
import { FeedbackTab } from "./student-tabs/FeedbackTab";
import { HomeworkTab } from "./student-tabs/HomeworkTab";
import { PlansTab } from "./student-tabs/PlansTab";
import { SessionsTab } from "./student-tabs/SessionsTab";

const TABS = [
  { key: "sessions", label: "Sessions" },
  { key: "documents", label: "Documents" },
  { key: "homework", label: "Homework" },
  { key: "feedback", label: "Feedback" },
  { key: "plans", label: "Plans" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function StudentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>("sessions");

  const { data: student, isLoading } = useQuery({
    queryKey: ["students", id],
    queryFn: () => directus.request(readItem("students", id ?? "")),
    enabled: Boolean(id),
  });

  if (!id) {
    return <p className={styles.status}>No student selected.</p>;
  }

  return (
    <div>
      <Link to="/" className={styles.back}>
        ← All students
      </Link>

      {isLoading ? <p className={styles.status}>Loading student…</p> : null}

      {student ? (
        <header className={styles.header}>
          <h1 className={styles.name}>{student.name}</h1>
          <p className={styles.meta}>
            {student.level ?? "No level set"} · {student.status}
          </p>
        </header>
      ) : null}

      <nav className={styles.tabs}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={tab.key === activeTab ? styles.tabActive : styles.tab}
            onClick={() => {
              setActiveTab(tab.key);
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className={styles.panel}>
        {activeTab === "sessions" ? <SessionsTab studentId={id} /> : null}
        {activeTab === "documents" ? <DocumentsTab studentId={id} /> : null}
        {activeTab === "homework" ? <HomeworkTab studentId={id} /> : null}
        {activeTab === "feedback" ? <FeedbackTab studentId={id} /> : null}
        {activeTab === "plans" ? <PlansTab studentId={id} /> : null}
      </div>
    </div>
  );
}
