import { Check, Copy } from "lucide-react";
import { toast } from "sonner";

import { Button, Field, Input } from "@/components/ui";

import { generatePassword } from "./password";
import styles from "./PasswordField.module.css";

async function copy(password: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(password);
    toast.success("Copied");
  } catch {
    toast.error("This browser would not let the page copy it. Select it and copy it by hand.");
  }
}

export interface PasswordFieldProps {
  value: string;
  onChange: (value: string) => void;
  error: string | null;
  autoFocus?: boolean;
}

/** The password being set: typed or generated, and copyable before it is sent. */
export function PasswordField({ value, onChange, error, autoFocus }: PasswordFieldProps) {
  return (
    <Field label="Password" required help="Copy it now — it is not shown again." error={error}>
      <div className={styles.row}>
        <Input
          className={styles.password}
          value={value}
          autoComplete="off"
          spellCheck={false}
          autoFocus={autoFocus ?? false}
          onChange={(event) => {
            onChange(event.target.value);
          }}
        />
        <Button
          onClick={() => {
            onChange(generatePassword());
          }}
        >
          Generate
        </Button>
        <Button
          disabled={value === ""}
          onClick={() => {
            void copy(value);
          }}
        >
          <Copy size={14} aria-hidden="true" />
          Copy
        </Button>
      </div>
    </Field>
  );
}

/**
 * The step between saving and closing: the password stays on screen until whoever set it
 * says they have it, because nothing will show it again.
 */
export function PasswordHandover({ password, what }: { password: string; what: string }) {
  return (
    <div className={styles.handover}>
      <p className={styles.done}>
        <Check size={16} aria-hidden="true" />
        {what}
      </p>
      <div className={styles.row}>
        <Input className={styles.password} value={password} readOnly aria-label="The password" />
        <Button
          variant="primary"
          onClick={() => {
            void copy(password);
          }}
        >
          <Copy size={14} aria-hidden="true" />
          Copy
        </Button>
      </div>
      <p className={styles.note}>
        Copy it and give it to them now. It is not shown again, and a lost one is replaced
        rather than found.
      </p>
    </div>
  );
}
