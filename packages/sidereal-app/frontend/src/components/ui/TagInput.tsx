import { X } from "lucide-react";
import { useState } from "react";
import type { KeyboardEvent } from "react";

import { cx } from "@/lib/cx";

import { useFieldControl } from "./field-context";
import controlStyles from "./control.module.css";
import styles from "./TagInput.module.css";

export interface TagInputProps {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function TagInput({ value, onChange, placeholder, disabled = false, className }: TagInputProps) {
  const field = useFieldControl();
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const tag = raw.trim();
    if (!tag || value.includes(tag)) {
      setDraft("");
      return;
    }
    onChange([...value, tag]);
    setDraft("");
  };

  const remove = (tag: string) => {
    onChange(value.filter((existing) => existing !== tag));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      add(draft);
      return;
    }
    if (event.key === "Backspace" && draft === "" && value.length > 0) {
      event.preventDefault();
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className={cx(controlStyles.control, styles.wrapper, className)} aria-invalid={field["aria-invalid"]}>
      {value.map((tag) => (
        <span key={tag} className={styles.tag}>
          {tag}
          <button
            type="button"
            className={styles.remove}
            onClick={() => {
              remove(tag);
            }}
            disabled={disabled}
            aria-label={`Remove ${tag}`}
          >
            <X size={12} aria-hidden="true" />
          </button>
        </span>
      ))}
      <input
        {...field}
        className={styles.input}
        value={draft}
        placeholder={value.length === 0 ? placeholder : undefined}
        disabled={disabled}
        onChange={(event) => {
          setDraft(event.target.value);
        }}
        onKeyDown={handleKeyDown}
        onBlur={() => {
          add(draft);
        }}
      />
    </div>
  );
}
