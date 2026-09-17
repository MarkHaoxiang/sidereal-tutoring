import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { PasswordField, PasswordHandover } from "@/components/students/PasswordField";
import { Button, Dialog, Field, Input } from "@/components/ui";
import { ApiError, apiError } from "@/lib/api";
import { useCreateTutor, useResetTutorPassword } from "@/lib/queries";
import type { TutorAccount } from "@/lib/queries";

import styles from "./admin.module.css";

export interface TutorDialogProps {
  open: boolean;
  onClose: () => void;
  /** "create" asks for the name and email too; "reset" only sets a new password. */
  mode: "create" | "reset";
  tutor?: TutorAccount | null;
}

export function TutorDialog({ open, onClose, mode, tutor }: TutorDialogProps) {
  const createTutor = useCreateTutor();
  const resetPassword = useResetTutorPassword();
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  // Set, and still on screen: the dialog stays open on the password until it is copied.
  const [handed, setHanded] = useState<string | null>(null);
  const wasOpen = useRef(false);

  // Clear the form as the dialog opens, so a password from a previous visit is never
  // offered again as if it were the live one.
  useEffect(() => {
    if (open && !wasOpen.current) {
      setEmail("");
      setFirstName("");
      setLastName("");
      setPassword("");
      setEmailError(null);
      setPasswordError(null);
      setHanded(null);
    }
    wasOpen.current = open;
  }, [open]);

  const creating = mode === "create";
  const pending = createTutor.isPending || resetPassword.isPending;

  const save = async () => {
    const address = email.trim();
    if (creating && !address.includes("@")) {
      setEmailError("Enter the email address the tutor will sign in with.");
      return;
    }
    if (password.length < 8) {
      setPasswordError("At least 8 characters — or use Generate.");
      return;
    }
    try {
      if (creating) {
        await createTutor.mutateAsync({
          email: address,
          password,
          first_name: firstName.trim() || null,
          last_name: lastName.trim() || null,
        });
        toast.success("Tutor added");
      } else {
        if (!tutor) {
          return;
        }
        await resetPassword.mutateAsync({ userId: tutor.user_id, password });
        toast.success("Saved");
      }
      setHanded(password);
    } catch (error) {
      const code = error instanceof ApiError ? error.code : undefined;
      const message = apiError(error);
      if (code === "invalid_email" || code === "tutor_refused") {
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
      title={creating ? "Add a tutor" : "Reset password"}
      busy={pending}
      footer={
        handed !== null ? (
          <Button variant="primary" onClick={onClose}>
            I have copied it
          </Button>
        ) : (
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
              {creating ? "Add tutor" : "Save password"}
            </Button>
          </>
        )
      }
    >
      {handed !== null ? (
        <PasswordHandover
          password={handed}
          what={creating ? "The tutor is added." : "The password is changed."}
        />
      ) : (
        <>
          {creating ? (
            <>
              <Field label="Email" required help="They sign in with this address." error={emailError}>
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
              <div className={styles.nameRow}>
                <Field label="First name" className={styles.nameField}>
                  <Input
                    value={firstName}
                    autoComplete="off"
                    onChange={(event) => {
                      setFirstName(event.target.value);
                    }}
                  />
                </Field>
                <Field label="Last name" className={styles.nameField}>
                  <Input
                    value={lastName}
                    autoComplete="off"
                    onChange={(event) => {
                      setLastName(event.target.value);
                    }}
                  />
                </Field>
              </div>
            </>
          ) : null}

          <PasswordField
            value={password}
            error={passwordError}
            autoFocus={!creating}
            onChange={(next) => {
              setPassword(next);
              setPasswordError(null);
            }}
          />
        </>
      )}
    </Dialog>
  );
}
