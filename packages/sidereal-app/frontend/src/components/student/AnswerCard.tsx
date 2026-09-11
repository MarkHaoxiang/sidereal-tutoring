import { useState } from "react";
import { toast } from "sonner";

import { Button, Card, ConfirmDialog, Field, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useHandInHomework, useSaveAnswers } from "@/lib/queries";
import type { MyHomework } from "@/lib/queries";

import styles from "./student.module.css";

export function AnswerCard({ homework }: { homework: MyHomework }) {
  const saved = homework.submission ?? "";
  const [answers, setAnswers] = useState(saved);
  const [confirming, setConfirming] = useState(false);
  const save = useSaveAnswers();
  const handIn = useHandInHomework();

  // Assigned is the only status a student may write in; Directus enforces that, and the
  // page agrees with it rather than offering a control that would be refused.
  if (homework.status !== "assigned") {
    return (
      <Card title="Your answers">
        <div className={styles.answers}>
          <p className={styles.handedIn}>
            {homework.submitted_at
              ? `You handed this in on ${formatDateTime(homework.submitted_at)}.`
              : "This has been handed in."}
            {homework.status === "marked" ? " Your tutor has marked it." : " Your tutor has not marked it yet."}
          </p>
          {saved ? (
            <p className={styles.written}>{saved}</p>
          ) : (
            <p className={styles.handedIn}>You handed this in without writing anything.</p>
          )}
        </div>
      </Card>
    );
  }

  const saveDraft = async () => {
    try {
      await save.mutateAsync({ id: homework.id, submission: answers });
      toast.success("Draft saved");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <Card title="Your answers">
      <div className={styles.answers}>
        <Field
          label="Write your answers"
          help="Save a draft as often as you like. Hand in when you are done — after that your answers cannot be changed."
        >
          <Textarea
            rows={10}
            value={answers}
            onChange={(event) => {
              setAnswers(event.target.value);
            }}
          />
        </Field>

        <div className={styles.actions}>
          <Button
            variant="primary"
            disabled={answers.trim() === ""}
            onClick={() => {
              setConfirming(true);
            }}
          >
            Hand in
          </Button>
          <Button
            loading={save.isPending}
            disabled={answers === saved}
            onClick={() => {
              void saveDraft();
            }}
          >
            Save draft
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirming}
        onClose={() => {
          setConfirming(false);
        }}
        title="Hand this homework in?"
        message="Your tutor will see your answers, and you will not be able to change them afterwards."
        confirmLabel="Hand in"
        cancelLabel="Not yet"
        onConfirm={async () => {
          try {
            await handIn.mutateAsync({ id: homework.id, submission: answers });
          } catch (error) {
            toast.error(apiError(error));
            throw error;
          }
          toast.success("Handed in");
        }}
      />
    </Card>
  );
}
