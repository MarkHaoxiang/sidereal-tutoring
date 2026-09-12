import { X } from "lucide-react";
import { useMemo, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import { Spinner } from "@/components/ui";
import controlStyles from "@/components/ui/control.module.css";
import { cx } from "@/lib/cx";
import { useTopics } from "@/lib/queries";

import { BREADCRUMB_SEPARATOR, topicPaths } from "./tree";
import styles from "./topics.module.css";

export interface TopicPickerProps {
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
  className?: string;
}

/** Every topic with its ancestors, so "Quadratics" under "Algebra" is never the wrong one. */
export function TopicPicker({ value, onChange, disabled = false, className }: TopicPickerProps) {
  const { data: topics, isLoading } = useTopics();
  const [search, setSearch] = useState("");

  const options = useMemo(() => {
    const rows = topics ?? [];
    const paths = topicPaths(rows);
    return rows
      .map((topic) => ({
        id: topic.id,
        name: topic.name,
        ancestors: (paths.get(topic.id) ?? [topic.name]).slice(0, -1),
        search: (paths.get(topic.id) ?? [topic.name]).join(" ").toLowerCase(),
      }))
      .sort((a, b) => a.search.localeCompare(b.search));
  }, [topics]);

  const term = search.trim().toLowerCase();
  const matches = term ? options.filter((option) => option.search.includes(term)) : options;
  const chosen = options.filter((option) => value.includes(option.id));

  const toggle = (id: string) => {
    onChange(value.includes(id) ? value.filter((entry) => entry !== id) : [...value, id]);
    setSearch("");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const first = matches[0];
    if (event.key === "Enter" && first) {
      event.preventDefault();
      toggle(first.id);
      return;
    }
    const last = value[value.length - 1];
    if (event.key === "Backspace" && search === "" && last) {
      event.preventDefault();
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className={cx(styles.picker, className)}>
      <div className={cx(controlStyles.control, styles.selection)}>
        {chosen.map((topic) => (
          <span key={topic.id} className={styles.selected}>
            {topic.name}
            <button
              type="button"
              className={styles.remove}
              disabled={disabled}
              aria-label={`Remove ${topic.name}`}
              onClick={() => {
                toggle(topic.id);
              }}
            >
              <X size={12} aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          className={styles.search}
          value={search}
          disabled={disabled}
          placeholder={chosen.length === 0 ? "Search topics" : undefined}
          aria-label="Search topics"
          onChange={(event) => {
            setSearch(event.target.value);
          }}
          onKeyDown={handleKeyDown}
        />
      </div>

      {isLoading ? (
        <p className={styles.note}>
          <Spinner size="sm" /> Loading topics…
        </p>
      ) : null}

      {topics && topics.length === 0 ? (
        <p className={styles.note}>
          No topics yet. Build the tree on the <Link to="/topics">Topics</Link> page.
        </p>
      ) : null}

      {matches.length > 0 ? (
        <div className={styles.options}>
          {matches.map((option) => (
            <button
              key={option.id}
              type="button"
              className={styles.option}
              aria-pressed={value.includes(option.id)}
              disabled={disabled}
              onClick={() => {
                toggle(option.id);
              }}
            >
              {option.ancestors.length > 0 ? (
                <span className={styles.optionPath}>
                  {option.ancestors.join(BREADCRUMB_SEPARATOR)}
                  {BREADCRUMB_SEPARATOR}
                </span>
              ) : null}
              <span className={styles.optionName}>{option.name}</span>
            </button>
          ))}
        </div>
      ) : null}

      {topics && topics.length > 0 && matches.length === 0 ? (
        <p className={styles.note}>{`No topic matches “${search.trim()}”.`}</p>
      ) : null}
    </div>
  );
}
