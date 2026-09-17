import { useState } from "react";
import { toast } from "sonner";

import { TutorDialog } from "@/components/admin/TutorDialog";
import { Button, ConfirmDialog, EmptyState, PageHeader, SkeletonRows } from "@/components/ui";
import { apiError } from "@/lib/api";
import { cx } from "@/lib/cx";
import { formatDateTime } from "@/lib/format";
import { useMediaQuery } from "@/lib/media";
import { isServiceAccount, tutorName, useRemoveTutor, useSetTutorStatus, useTutors } from "@/lib/queries";
import type { TutorAccount } from "@/lib/queries";

import pageStyles from "../page.module.css";
import styles from "./table.module.css";

const WIDE = "(min-width: 40rem)";

export function AdminTutorsPage() {
  const { data: tutors, isLoading, isError } = useTutors();
  const setStatus = useSetTutorStatus();
  const removeTutor = useRemoveTutor();
  const wide = useMediaQuery(WIDE);
  const [adding, setAdding] = useState(false);
  const [resetting, setResetting] = useState<TutorAccount | null>(null);
  const [removing, setRemoving] = useState<TutorAccount | null>(null);

  const toggleStatus = async (tutor: TutorAccount) => {
    const next = tutor.status === "suspended" ? "active" : "suspended";
    try {
      await setStatus.mutateAsync({ userId: tutor.user_id, status: next });
      toast.success(
        next === "suspended" ? "Suspended" : "Reactivated"
      );
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <div>
      <PageHeader
        title="Tutors"
        actions={
          <Button
            variant="primary"
            onClick={() => {
              setAdding(true);
            }}
          >
            Add tutor
          </Button>
        }
      />

      {isLoading ? <SkeletonRows count={3} variant="line" label="Loading the tutors" /> : null}
      {isError ? <p className={pageStyles.status}>Could not load the tutors.</p> : null}

      {tutors && tutors.length === 0 ? (
        <EmptyState
          message="No tutors yet."
          action={
            <Button
              variant="primary"
              onClick={() => {
                setAdding(true);
              }}
            >
              Add tutor
            </Button>
          }
        />
      ) : null}

      {tutors && tutors.length > 0 && wide ? (
        <div className={styles.scroller} tabIndex={0} role="region" aria-label="Tutors">
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Tutor</th>
                <th scope="col">Status</th>
                <th scope="col" className={styles.numeric}>
                  Students
                </th>
                <th scope="col">Last signed in</th>
                <th scope="col">
                  <span className={styles.visuallyHidden}>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {tutors.map((tutor) => {
                const suspended = tutor.status === "suspended";
                const service = isServiceAccount(tutor);
                return (
                  <tr key={tutor.user_id}>
                    <td>
                      <span className={styles.primary}>{tutorName(tutor)}</span>
                      {tutor.email && tutor.email !== tutorName(tutor) ? (
                        <span className={styles.secondary}>{tutor.email}</span>
                      ) : null}
                    </td>
                    <td>
                      <span className={cx(styles.chip, suspended ? styles.chipDanger : styles.chipOk)}>
                        {suspended ? "Suspended" : "Active"}
                      </span>
                    </td>
                    <td className={styles.numeric}>
                      {service ? (
                        <span className={styles.secondaryCell}>Service account</span>
                      ) : (
                        tutor.students ?? 0
                      )}
                    </td>
                    <td className={styles.secondaryCell}>
                      {tutor.last_access ? formatDateTime(tutor.last_access) : "Never"}
                    </td>
                    <td>
                      {service ? null : (
                        <div className={styles.actions}>
                          <Button
                            size="sm"
                            onClick={() => {
                              setResetting(tutor);
                            }}
                          >
                            Reset password
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              void toggleStatus(tutor);
                            }}
                          >
                            {suspended ? "Reactivate" : "Suspend"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setRemoving(tutor);
                            }}
                          >
                            Remove
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {tutors && tutors.length > 0 && !wide ? (
        <div className={styles.cards} role="list" aria-label="Tutors">
          {tutors.map((tutor) => {
            const suspended = tutor.status === "suspended";
            const service = isServiceAccount(tutor);
            return (
              <article key={tutor.user_id} className={styles.card} role="listitem">
                <div className={styles.cardHeader}>
                  <div>
                    <span className={styles.primary}>{tutorName(tutor)}</span>
                    {tutor.email && tutor.email !== tutorName(tutor) ? (
                      <span className={styles.secondary}>{tutor.email}</span>
                    ) : null}
                  </div>
                  <span className={cx(styles.chip, suspended ? styles.chipDanger : styles.chipOk)}>
                    {suspended ? "Suspended" : "Active"}
                  </span>
                </div>

                {service ? (
                  <p className={styles.cardNote}>Service account</p>
                ) : (
                  <div className={styles.cardField}>
                    <span className={styles.cardFieldLabel}>Students</span>
                    <span>{tutor.students ?? 0}</span>
                  </div>
                )}

                <div className={styles.cardField}>
                  <span className={styles.cardFieldLabel}>Last signed in</span>
                  <span>{tutor.last_access ? formatDateTime(tutor.last_access) : "Never"}</span>
                </div>

                {service ? null : (
                  <div className={styles.cardActions}>
                    <Button
                      size="sm"
                      onClick={() => {
                        setResetting(tutor);
                      }}
                    >
                      Reset password
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        void toggleStatus(tutor);
                      }}
                    >
                      {suspended ? "Reactivate" : "Suspend"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setRemoving(tutor);
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      ) : null}

      <TutorDialog
        open={adding}
        mode="create"
        onClose={() => {
          setAdding(false);
        }}
      />

      <TutorDialog
        open={resetting !== null}
        mode="reset"
        tutor={resetting}
        onClose={() => {
          setResetting(null);
        }}
      />

      <ConfirmDialog
        open={removing !== null}
        onClose={() => {
          setRemoving(null);
        }}
        title={removing ? `Remove ${tutorName(removing)}?` : "Remove this tutor?"}
        message="Their sign-in goes for good. A tutor with students cannot be removed — hand those over first."
        confirmLabel="Remove"
        danger
        onConfirm={async () => {
          if (!removing) {
            return;
          }
          try {
            await removeTutor.mutateAsync(removing.user_id);
          } catch (error) {
            toast.error(apiError(error));
            throw error;
          }
          toast.success("Removed");
        }}
      />
    </div>
  );
}
