import { useState } from "react";

import { addedByName } from "@/components/material/authors";
import { LibraryTabs } from "@/components/material/LibraryTabs";
import { PaperRow } from "@/components/papers/PaperRow";
import { EmptyState, Input, PageHeader, SkeletonRows } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { usePapers } from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./LibraryPage.module.css";
import paperStyles from "@/components/papers/papers.module.css";

export function PapersPage() {
  const { user } = useAuth();
  const { data, isLoading, isError } = usePapers();
  const [search, setSearch] = useState("");

  const needle = search.trim().toLowerCase();
  const visible = (data ?? []).filter((paper) =>
    needle ? [paper.title, paper.board].some((value) => (value ?? "").toLowerCase().includes(needle)) : true
  );

  return (
    <div>
      <PageHeader
        title="Library"
        subtitle="Material every tutor can use."
      />

      <LibraryTabs />

      <div className={styles.toolbar}>
        <Input
          type="search"
          className={paperStyles.search}
          value={search}
          placeholder="Search by name or board"
          aria-label="Search the papers by name or board"
          onChange={(event) => {
            setSearch(event.target.value);
          }}
        />
      </div>

      {isLoading ? <SkeletonRows count={3} label="Loading the papers" /> : null}
      {isError ? <p className={pageStyles.status}>Could not load the papers.</p> : null}

      {data && visible.length === 0 ? (
        <EmptyState
          message={
            needle
              ? "Nothing matches."
              : "No papers yet — extract one from material in the library."
          }
        />
      ) : null}

      {visible.length > 0 ? (
        <ul className={paperStyles.list}>
          {visible.map((paper) => (
            <PaperRow key={paper.id} paper={paper} addedBy={addedByName(paper.user_created, user?.id ?? null)} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}
