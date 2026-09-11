import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button, Dialog, Field, Input } from "@/components/ui";
import { ApiError, apiError } from "@/lib/api";
import { useCreateStudentLogin, useResetStudentPassword } from "@/lib/queries";

import { generatePassword } from "./password";
import styles from "./students.module.css";

const PASSWORD_HELP =
  "Copy this password now and give it to the student — it is not shown again. You can set a new one whenever you need to.";

export interface LoginDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: string;
  studentName: string;
  /** "create" asks for an email too; "reset" only changes the password of a login that exists. */
  mode: "create" | "reset";
}

export function LoginDialog({ open, onClose, studentId, studentName, mode }: LoginDialogProps) {
  const createLogin = useCreateStudentLogin();
  const resetPassword = useResetStudentPassword();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const wasOpen = useRef(false);

  // Clear the form as the dialog opens, so a password from a previous visit is never
  // offered again as if it were the live one.
  useEffect(() => {
    if (open && !wasOpen.current) {
      setEmail("");
      setPassword("");
      setEmailError(null);
      setPasswordError(null);
    }
    wasOpen.current = open;
  }, [open]);

  const pending = createLogin.isPending || resetPassword.isPending;
  const creating = mode === "create";

  const save = async () => {
    const address = email.trim();
    if (creating && !address.includes("@")) {
      setEmailError("Enter the email address the student will sign in with.");
      return;
    }
    if (password.length < 8) {
      setPasswordError("A password needs at least 8 characters. Generate takes care of it for you.");
      return;
    }
    try {
      if (creating) {
        await createLogin.mutateAsync({ studentId, email: address, password });
        toast.success(`${studentName} can sign in now`);
      } else {
        await resetPassword.mutateAsync({ studentId, password });
        toast.success("New password saved");
      }
      onClose();
    } catch (error) {
      const code = error instanceof ApiError ? error.code : undefined;
      const message = apiError(error);
      if (code === "invalid_email" || code === "login_exists") {
        setEmailError(message);
      } else if (code === "weak_password") {
        setPasswordError(message);
      } else {
        toast.error(message);
      }
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={creating ? "Set up a login" : "Reset password"}
      busy={pending}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={pending}
            onClick={() => {
              void save();
            }}
          >
            {creating ? "Create login" : "Save password"}
          </Button>
        </>
      }
    >
      {creating ? (
        <Field
          label="Email"
          required
          help={`${studentName} signs in with this address.`}
          error={emailError}
        >
          <Input
            type="email"
            value={email}
            autoFocus
            autoComplete="off"
            onChange={(event) => {
              setEmail(event.target.value);
              setEmailError(null);
            }}
          />
        </Field>
      ) : null}
      <Field label="Password" required help={PASSWORD_HELP} error={passwordError}>
        <div className={styles.passwordRow}>
          <Input
            className={styles.password}
            value={password}
            autoComplete="off"
            spellCheck={false}
            autoFocus={!creating}
            onChange={(event) => {
              setPassword(event.target.value);
              setPasswordError(null);
            }}
          />
          <Button
            onClick={() => {
              setPassword(generatePassword());
              setPasswordError(null);
            }}
          >
            Generate
          </Button>
        </div>
      </Field>
    </Dialog>
  );
}
