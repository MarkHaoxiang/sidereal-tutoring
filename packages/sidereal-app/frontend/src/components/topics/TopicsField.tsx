import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui";
import { apiError } from "@/lib/api";

import { TopicChips } from "./TopicChips";
import { TopicPicker } from "./TopicPicker";
import styles from "./topics.module.css";

export interface TopicsFieldProps {
  topics: { id: string; name: string }[];
  onSave: (topicIds: string[]) => Promise<void>;
  /** False where the caller may read the tags but not change them. */
  editable?: boolean;
}

export function TopicsField({ topics, onSave, editable = true }: TopicsFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await onSave(draft);
      toast.success("Topics saved");
      setEditing(false);
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.field}>
      <div className={styles.fieldHeader}>
        <h2 className={styles.fieldTitle}>Topics</h2>
        {editing || !editable ? null : (
          <Button
            size="sm"
            onClick={() => {
              setDraft(topics.map((topic) => topic.id));
              setEditing(true);
            }}
          >
            Edit
          </Button>
        )}
      </div>

      {editing ? (
        <>
          <TopicPicker value={draft} onChange={setDraft} disabled={saving} />
          <div className={styles.actions}>
            <Button
              variant="primary"
              loading={saving}
              onClick={() => {
                void save();
              }}
            >
              Save
            </Button>
            <Button
              variant="ghost"
              disabled={saving}
              onClick={() => {
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </>
      ) : (
        <TopicChips topics={topics} empty="Not tagged with any topic yet." />
      )}
    </div>
  );
}
