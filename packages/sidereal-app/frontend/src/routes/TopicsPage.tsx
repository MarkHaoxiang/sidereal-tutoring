import { ChevronDown, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { toast } from "sonner";

import { breadcrumb, buildTopicTree, topicPaths } from "@/components/topics/tree";
import type { TopicNode } from "@/components/topics/tree";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  SkeletonRows,
  Textarea,
} from "@/components/ui";
import { apiError } from "@/lib/api";
import { cx } from "@/lib/cx";
import { useCreateTopic, useDeleteTopic, useTopicUsage, useTopics, useUpdateTopic } from "@/lib/queries";
import type { TopicRow } from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./TopicsPage.module.css";

function indent(depth: number): CSSProperties {
  return { "--depth": String(depth) } as CSSProperties;
}

export function TopicsPage() {
  const { data: topics, isLoading, isError } = useTopics();
  const create = useCreateTopic();
  const update = useUpdateTopic();
  const remove = useDeleteTopic();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const [addingUnder, setAddingUnder] = useState<{ parent: string | null } | null>(null);
  const [newName, setNewName] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameTo, setRenameTo] = useState("");
  const [deleting, setDeleting] = useState<TopicRow | null>(null);
  const [description, setDescription] = useState("");
  const [savingDescription, setSavingDescription] = useState(false);

  const rows = useMemo(() => topics ?? [], [topics]);
  const tree = useMemo(() => buildTopicTree(rows), [rows]);
  const paths = useMemo(() => topicPaths(rows), [rows]);
  const selected = rows.find((row) => row.id === selectedId) ?? null;
  const usage = useTopicUsage(selected?.id ?? null);

  // The description belongs to the selected topic, so the draft follows the selection rather
  // than outliving it.
  useEffect(() => {
    setDescription(selected?.description ?? "");
  }, [selected?.id, selected?.description]);

  const addTopic = async (parent: string | null) => {
    const name = newName.trim();
    if (!name) {
      return;
    }
    try {
      const added = await create.mutateAsync({ name, parent });
      setNewName("");
      setAddingUnder(null);
      setSelectedId(added.id);
      toast.success(`“${name}” added`);
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const rename = async (id: string) => {
    const name = renameTo.trim();
    if (!name) {
      return;
    }
    try {
      await update.mutateAsync({ id, patch: { name } });
      setRenamingId(null);
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const saveDescription = async () => {
    if (!selected) {
      return;
    }
    setSavingDescription(true);
    try {
      await update.mutateAsync({ id: selected.id, patch: { description: description.trim() || null } });
      toast.success("Description saved");
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      setSavingDescription(false);
    }
  };

  const addRow = (parent: string | null, depth: number) => (
    <div className={styles.editRow} style={indent(depth)}>
      <Input
        className={styles.editInput}
        value={newName}
        autoFocus
        aria-label={parent === null ? "New topic name" : "New subtopic name"}
        placeholder="Name"
        onChange={(event) => {
          setNewName(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            void addTopic(parent);
          }
        }}
      />
      <Button
        variant="primary"
        size="sm"
        loading={create.isPending}
        onClick={() => {
          void addTopic(parent);
        }}
      >
        Add
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          setAddingUnder(null);
          setNewName("");
        }}
      >
        Cancel
      </Button>
    </div>
  );

  const renderNode = (node: TopicNode) => {
    const { topic, depth, children } = node;
    const isCollapsed = collapsed.includes(topic.id);
    return (
      <li key={topic.id}>
        {renamingId === topic.id ? (
          <div className={styles.editRow} style={indent(depth)}>
            <Input
              className={styles.editInput}
              value={renameTo}
              autoFocus
              aria-label={`New name for ${topic.name}`}
              onChange={(event) => {
                setRenameTo(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void rename(topic.id);
                }
              }}
            />
            <Button
              variant="primary"
              size="sm"
              loading={update.isPending}
              onClick={() => {
                void rename(topic.id);
              }}
            >
              Save
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRenamingId(null);
              }}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <div
            className={cx(styles.row, selectedId === topic.id && styles.rowSelected)}
            style={indent(depth)}
          >
            {children.length > 0 ? (
              <button
                type="button"
                className={styles.twist}
                aria-label={isCollapsed ? `Show what is under ${topic.name}` : `Hide what is under ${topic.name}`}
                aria-expanded={!isCollapsed}
                onClick={() => {
                  setCollapsed((current) =>
                    current.includes(topic.id)
                      ? current.filter((entry) => entry !== topic.id)
                      : [...current, topic.id]
                  );
                }}
              >
                {isCollapsed ? (
                  <ChevronRight size={15} aria-hidden="true" />
                ) : (
                  <ChevronDown size={15} aria-hidden="true" />
                )}
              </button>
            ) : (
              <span className={styles.twistSpacer} />
            )}

            <button
              type="button"
              className={styles.name}
              aria-current={selectedId === topic.id || undefined}
              onClick={() => {
                setSelectedId(topic.id);
              }}
            >
              {topic.name}
            </button>

            <span className={styles.rowActions}>
              <button
                type="button"
                className={styles.iconButton}
                aria-label={`Add a subtopic under ${topic.name}`}
                onClick={() => {
                  setNewName("");
                  setAddingUnder({ parent: topic.id });
                  setCollapsed((current) => current.filter((entry) => entry !== topic.id));
                }}
              >
                <Plus size={15} aria-hidden="true" />
              </button>
              <button
                type="button"
                className={styles.iconButton}
                aria-label={`Rename ${topic.name}`}
                onClick={() => {
                  setRenameTo(topic.name);
                  setRenamingId(topic.id);
                }}
              >
                <Pencil size={14} aria-hidden="true" />
              </button>
              <button
                type="button"
                className={styles.iconButton}
                aria-label={`Delete ${topic.name}`}
                onClick={() => {
                  setDeleting(topic);
                }}
              >
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </span>
          </div>
        )}

        {addingUnder?.parent === topic.id ? addRow(topic.id, depth + 1) : null}

        {children.length > 0 && !isCollapsed ? (
          <ul className={styles.subtree}>{children.map(renderNode)}</ul>
        ) : null}
      </li>
    );
  };

  const counts: { label: string; value: number }[] = [
    { label: "Material", value: usage.data?.documents ?? 0 },
    { label: "Questions", value: usage.data?.questions ?? 0 },
    { label: "Homework", value: usage.data?.homework ?? 0 },
  ];

  return (
    <div>
      <PageHeader
        title="Topics"
        subtitle="The tree you tag material, questions and homework with. It is yours to shape — there is no syllabus behind it."
        actions={
          <Button
            variant="primary"
            onClick={() => {
              setNewName("");
              setAddingUnder({ parent: null });
            }}
          >
            Add topic
          </Button>
        }
      />

      {isLoading ? <SkeletonRows count={5} variant="line" label="Loading your topics" /> : null}
      {isError ? <p className={pageStyles.status}>Could not load topics. Try refreshing the page.</p> : null}

      {topics && rows.length === 0 && addingUnder === null ? (
        <EmptyState
          message="No topics yet. Start with a broad one — Algebra, say — and add what sits under it."
          action={
            <Button
              variant="primary"
              onClick={() => {
                setNewName("");
                setAddingUnder({ parent: null });
              }}
            >
              Add topic
            </Button>
          }
        />
      ) : null}

      {topics && (rows.length > 0 || addingUnder !== null) ? (
        <div className={styles.split}>
          <div className={styles.panel}>
            <ul className={styles.tree}>{tree.map(renderNode)}</ul>
            {addingUnder?.parent === null ? (
              <div className={styles.rootAdd}>{addRow(null, 0)}</div>
            ) : null}
          </div>

          <div className={styles.panel}>
            {selected ? (
              <>
                {(paths.get(selected.id)?.length ?? 0) > 1 ? (
                  <p className={styles.breadcrumb}>{breadcrumb(paths.get(selected.id)?.slice(0, -1))}</p>
                ) : null}
                <h2 className={styles.detailTitle}>{selected.name}</h2>

                <Field label="Description" help="What this topic covers, in your own words.">
                  <Textarea
                    rows={5}
                    value={description}
                    onChange={(event) => {
                      setDescription(event.target.value);
                    }}
                  />
                </Field>
                <div className={styles.detailActions}>
                  <Button
                    variant="primary"
                    loading={savingDescription}
                    disabled={description === (selected.description ?? "")}
                    onClick={() => {
                      void saveDescription();
                    }}
                  >
                    Save description
                  </Button>
                </div>

                <dl className={styles.counts}>
                  {counts.map((count) => (
                    <div key={count.label} className={styles.count}>
                      <dd className={styles.countValue}>{count.value}</dd>
                      <dt className={styles.countLabel}>{count.label}</dt>
                    </div>
                  ))}
                </dl>
              </>
            ) : (
              <p className={pageStyles.status}>
                Choose a topic to see what it covers and how much is tagged with it.
              </p>
            )}
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => {
          setDeleting(null);
        }}
        title={deleting ? `Delete “${deleting.name}”?` : "Delete this topic?"}
        message="Anything under it is kept and moves up to the top level. Material, questions and homework tagged with it lose that tag and are otherwise untouched."
        confirmLabel="Delete"
        danger
        onConfirm={async () => {
          if (!deleting) {
            return;
          }
          try {
            await remove.mutateAsync(deleting.id);
          } catch (error) {
            toast.error(apiError(error));
            throw error;
          }
          if (selectedId === deleting.id) {
            setSelectedId(null);
          }
          toast.success("Topic deleted");
        }}
      />
    </div>
  );
}
