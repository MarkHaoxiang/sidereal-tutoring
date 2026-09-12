import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button, Card, Field, Input } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useAuth, userDisplayName } from "@/lib/auth-context";
import { useRemoveAvatar, useSaveAvatar, useSaveProfile } from "@/lib/queries";

import { Avatar } from "./Avatar";
import styles from "./account.module.css";

// Big enough for a photo straight off a phone, small enough that the wait is short.
const MAX_PHOTO_BYTES = 8 * 1024 * 1024;

export function ProfileCard() {
  const { user } = useAuth();
  const saveProfile = useSaveProfile();
  const saveAvatar = useSaveAvatar();
  const removeAvatar = useRemoveAvatar();
  const fileInput = useRef<HTMLInputElement>(null);

  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [emailError, setEmailError] = useState<string | null>(null);

  // Whatever is on the account is what the fields show; a save that changes it, or
  // another tab that does, brings them back into step.
  useEffect(() => {
    setFirstName(user?.first_name ?? "");
    setLastName(user?.last_name ?? "");
    setEmail(user?.email ?? "");
    setEmailError(null);
  }, [user?.first_name, user?.last_name, user?.email]);

  if (!user) {
    return null;
  }

  const photoPending = saveAvatar.isPending || removeAvatar.isPending;
  const changed =
    firstName !== (user.first_name ?? "") || lastName !== (user.last_name ?? "") || email !== (user.email ?? "");

  const save = async () => {
    const address = email.trim();
    if (!address.includes("@")) {
      setEmailError("Enter the email address you sign in with.");
      return;
    }
    try {
      await saveProfile.mutateAsync({
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        email: address,
      });
      toast.success("Your details are saved");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const choosePhoto = async (file: File) => {
    if (!file.type.startsWith("image/")) {
      toast.error("That file is not an image. Choose a photo instead.");
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      toast.error("That photo is too large. Choose one under 8 MB.");
      return;
    }
    try {
      await saveAvatar.mutateAsync(file);
      toast.success("Your photo is saved");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const remove = async () => {
    try {
      await removeAvatar.mutateAsync();
      toast.success("Your photo is removed");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <Card title="Profile">
      <div className={styles.photo}>
        <Avatar name={userDisplayName(user)} fileId={user.avatar} />
        <div className={styles.photoActions}>
          <div className={styles.photoButtons}>
            <Button
              loading={saveAvatar.isPending}
              disabled={photoPending}
              onClick={() => {
                fileInput.current?.click();
              }}
            >
              Change photo
            </Button>
            {user.avatar ? (
              <Button
                variant="ghost"
                loading={removeAvatar.isPending}
                disabled={photoPending}
                onClick={() => {
                  void remove();
                }}
              >
                Remove
              </Button>
            ) : null}
          </div>
          <p className={styles.hint}>A square photo looks best. It is shown to you, and to nobody else.</p>
        </div>
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          className={styles.fileInput}
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Cleared so choosing the same file again still counts as a change.
            event.target.value = "";
            if (file) {
              void choosePhoto(file);
            }
          }}
        />
      </div>

      <div className={styles.form}>
        <div className={styles.row}>
          <Field label="First name" className={styles.rowField}>
            <Input
              value={firstName}
              autoComplete="given-name"
              onChange={(event) => {
                setFirstName(event.target.value);
              }}
            />
          </Field>
          <Field label="Last name" className={styles.rowField}>
            <Input
              value={lastName}
              autoComplete="family-name"
              onChange={(event) => {
                setLastName(event.target.value);
              }}
            />
          </Field>
        </div>

        <Field label="Email" required help="You sign in with this address." error={emailError}>
          <Input
            type="email"
            value={email}
            autoComplete="email"
            onChange={(event) => {
              setEmail(event.target.value);
              setEmailError(null);
            }}
          />
        </Field>

        <div className={styles.actions}>
          <Button
            variant="primary"
            loading={saveProfile.isPending}
            disabled={!changed}
            onClick={() => {
              void save();
            }}
          >
            Save
          </Button>
        </div>
      </div>
    </Card>
  );
}
