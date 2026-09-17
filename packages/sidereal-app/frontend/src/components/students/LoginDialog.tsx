import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button, Dialog, Field, Input } from "@/components/ui";
import { ApiError, apiError } from "@/lib/api";
import { useCreateStudentLogin, useResetStudentPassword } from "@/lib/queries";

import { PasswordField, PasswordHandover } from "./PasswordField";

export interface LoginDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: string;
  /** "create" asks for an email too; "reset" only changes the password of a login that exists. */
  mode: "create" | "reset";
}

export function LoginDialog({ open, onClose, studentId, mode }: LoginDialogProps) {
  const createLogin = useCreateStudentLogin();
  const resetPassword = useResetStudentPassword();
  const [email, setEmail] = useState("");
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
      setPassword("");
      setEmailError(null);
      setPasswordError(null);
      setHanded(null);
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
      setPasswordError("At least 8 characters — or use Generate.");
      return;
    }
    try {
      if (creating) {
        await createLogin.mutateAsync({ studentId, email: address, password });
        toast.success("Login created");
      } else {
        await resetPassword.mutateAsync({ studentId, password });
        toast.success("Saved");
      }
      setHanded(password);
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
              {creating ? "Create login" : "Save password"}
            </Button>
          </>
        )
      }
    >
      {handed !== null ? (
        <PasswordHandover
          password={handed}
          what={creating ? "The login is set up." : "The password is changed."}
        />
      ) : (
        <>
          {creating ? (
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
