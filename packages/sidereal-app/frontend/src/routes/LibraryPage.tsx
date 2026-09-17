import { useMemo, useState } from "react";

import { AddMaterialDialog } from "@/components/material/AddMaterialDialog";
import { addedByName } from "@/components/material/authors";
import { libraryTopics, libraryTopicsOf, matchesLibraryFilter } from "@/components/material/library";
import { LibraryTabs } from "@/components/material/LibraryTabs";
import { MaterialRow } from "@/components/material/MaterialRow";
import { TopicFilter } from "@/components/topics/TopicFilter";
import { Button, EmptyState, Input, PageHeader, SkeletonRows } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { useLibraryDocuments } from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./LibraryPage.module.css";

export function LibraryPage() {
  const { user } = useAuth();
  const { data, isLoading, isError } = useLibraryDocuments();
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const documents = useMemo(() => data ?? [], [data]);
  const topics = useMemo(() => libraryTopics(documents), [documents]);
  const visible = documents.filter((row) => matchesLibraryFilter(row, { search, topic }));

  const add = (
    <Button
      variant="primary"
      onClick={() => {
        setAdding(true);
      }}
    >
      Add material
    </Button>
  );

  return (
    <div>
      <PageHeader
        title="Library"
        subtitle="Material every tutor can use."
        actions={add}
      />

      <LibraryTabs />

      <div className={styles.toolbar}>
        <Input
          type="search"
          value={search}
          placeholder="Search by name"
          aria-label="Search the library by name"
          onChange={(event) => {
            setSearch(event.target.value);
          }}
        />
        <TopicFilter topics={topics} value={topic} onChange={setTopic} />
      </div>

      {isLoading ? <SkeletonRows count={4} label="Loading the library" /> : null}
      {isError ? <p className={pageStyles.status}>Could not load the library.</p> : null}

      {data && visible.length === 0 ? (
        <EmptyState
          message={
            search.trim() || topic
              ? "Nothing matches."
              : "The library is empty."
          }
          action={search.trim() || topic ? null : add}
        />
      ) : null}

      {visible.length > 0 ? (
        <ul className={styles.list}>
          {visible.map((document) => (
            <MaterialRow
              key={document.id}
              document={document}
              to={`/library/${document.id}`}
              topics={libraryTopicsOf(document)}
              addedBy={addedByName(document.user_created, user?.id ?? null)}
            />
          ))}
        </ul>
      ) : null}

      <AddMaterialDialog
        open={adding}
        onClose={() => {
          setAdding(false);
        }}
      />
    </div>
  );
}
