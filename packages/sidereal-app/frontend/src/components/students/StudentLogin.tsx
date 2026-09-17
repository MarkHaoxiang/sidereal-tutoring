import { useState } from "react";
import { toast } from "sonner";

import { Button, ConfirmDialog } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useRemoveStudentLogin } from "@/lib/queries";

import { LoginDialog } from "./LoginDialog";
import styles from "./students.module.css";

export interface StudentLoginProps {
  studentId: string;
  studentName: string;
  /** The linked `directus_users` id, or null while the student has no login at all. */
  userId: string | null;
  /** The address they sign in with, once it has been read. */
  email: string | null;
}

export function StudentLogin({ studentId, studentName, userId, email }: StudentLoginProps) {
  const [dialog, setDialog] = useState<"create" | "reset" | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const removeLogin = useRemoveStudentLogin();

  const remove = async () => {
    try {
      await removeLogin.mutateAsync(studentId);
      toast.success("Login removed");
    } catch (error) {
      toast.error(apiError(error));
      throw error;
    }
  };

  return (
    <>
      <p className={styles.login}>
        <span className={styles.loginLabel}>Login</span>
        <span className={styles.separator} aria-hidden="true">
          ·
        </span>
        {userId ? (
          <>
            <span className={styles.email}>{email ?? "Login set up"}</span>
            <span className={styles.separator} aria-hidden="true">
              ·
            </span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDialog("reset");
              }}
            >
              Reset password
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setConfirmRemove(true);
              }}
            >
              Remove login
            </Button>
          </>
        ) : (
          <>
            <span>No login yet</span>
            <span className={styles.separator} aria-hidden="true">
              ·
            </span>
            <Button
              size="sm"
              onClick={() => {
                setDialog("create");
              }}
            >
              Set up login
            </Button>
          </>
        )}
      </p>

      <LoginDialog
        open={dialog !== null}
        onClose={() => {
          setDialog(null);
        }}
        studentId={studentId}
        mode={dialog ?? "create"}
      />

      <ConfirmDialog
        open={confirmRemove}
        onClose={() => {
          setConfirmRemove(false);
        }}
        title="Remove this login?"
        message={`${studentName} will not be able to sign in any more. Everything they handed in is kept, and you can set up a new login later.`}
        confirmLabel="Remove login"
        danger
        onConfirm={remove}
      />
    </>
  );
}
