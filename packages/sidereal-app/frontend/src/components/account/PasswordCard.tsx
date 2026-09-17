import { useState } from "react";
import { toast } from "sonner";

import { Button, Card, Field, Input } from "@/components/ui";
import { ApiError, apiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useChangePassword, WRONG_PASSWORD } from "@/lib/queries";

import styles from "./account.module.css";

const MIN_LENGTH = 8;

export function PasswordCard() {
  const { user } = useAuth();
  const changePassword = useChangePassword();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [currentError, setCurrentError] = useState<string | null>(null);
  const [nextError, setNextError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const email = user?.email ?? null;

  const save = async () => {
    if (!email) {
      return;
    }
    if (!current) {
      setCurrentError("Enter the password you use now.");
      return;
    }
    if (next.length < MIN_LENGTH) {
      setNextError(`A new password needs at least ${String(MIN_LENGTH)} characters.`);
      return;
    }
    if (next !== confirm) {
      setConfirmError("These two do not match.");
      return;
    }
    try {
      await changePassword.mutateAsync({ email, current, next });
    } catch (error) {
      if (error instanceof ApiError && error.code === WRONG_PASSWORD) {
        setCurrentError(error.message);
        return;
      }
      toast.error(apiError(error));
      return;
    }
    setCurrent("");
    setNext("");
    setConfirm("");
    toast.success("Password changed");
  };

  return (
    <Card title="Password">
      <div className={styles.form}>
        <Field label="Current password" required error={currentError}>
          <Input
            type="password"
            value={current}
            autoComplete="current-password"
            onChange={(event) => {
              setCurrent(event.target.value);
              setCurrentError(null);
            }}
          />
        </Field>

        <div className={styles.row}>
          <Field
            label="New password"
            required
            className={styles.rowField}
            help={`At least ${String(MIN_LENGTH)} characters.`}
            error={nextError}
          >
            <Input
              type="password"
              value={next}
              autoComplete="new-password"
              onChange={(event) => {
                setNext(event.target.value);
                setNextError(null);
              }}
            />
          </Field>
          <Field label="Repeat new password" required className={styles.rowField} error={confirmError}>
            <Input
              type="password"
              value={confirm}
              autoComplete="new-password"
              onChange={(event) => {
                setConfirm(event.target.value);
                setConfirmError(null);
              }}
            />
          </Field>
        </div>

        <div className={styles.actions}>
          <Button
            variant="primary"
            loading={changePassword.isPending}
            disabled={!email}
            onClick={() => {
              void save();
            }}
          >
            Change password
          </Button>
          <p className={styles.hint}>You stay signed in here.</p>
        </div>
      </div>
    </Card>
  );
}
