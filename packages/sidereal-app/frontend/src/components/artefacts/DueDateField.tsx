import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Field, Input } from "@/components/ui";
import { apiError } from "@/lib/api";

import styles from "./artefacts.module.css";

export interface DueDateFieldProps {
  value: string | null;
  onSave: (due: string | null) => Promise<void>;
}

export function DueDateField({ value, onSave }: DueDateFieldProps) {
  const [due, setDue] = useState(value ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDue(value ?? "");
  }, [value]);

  const change = async (next: string) => {
    setDue(next);
    setSaving(true);
    try {
      await onSave(next || null);
      toast.success(next ? "Saved" : "Cleared");
    } catch (error) {
      toast.error(apiError(error));
      setDue(value ?? "");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.section}>
      <Field label="Due date">
        <Input
          type="date"
          value={due}
          disabled={saving}
          onChange={(event) => {
            void change(event.target.value);
          }}
        />
      </Field>
    </div>
  );
}
