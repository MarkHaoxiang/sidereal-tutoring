import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button, Dialog, Field, Input, TagInput, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useCreateStudent, useUpdateStudent } from "@/lib/queries";
import type { StudentDetail } from "@/lib/queries";

interface Draft {
  name: string;
  level: string;
  subjects: string[];
  notes: string;
}

function toDraft(student: StudentDetail | null | undefined): Draft {
  return {
    name: student?.name ?? "",
    level: student?.level ?? "",
    subjects: student?.subjects ?? [],
    notes: student?.notes ?? "",
  };
}

export interface StudentDialogProps {
  open: boolean;
  onClose: () => void;
  /** Omit to add a student; pass one to edit it. */
  student?: StudentDetail | null;
}

export function StudentDialog({ open, onClose, student }: StudentDialogProps) {
  const createStudent = useCreateStudent();
  const updateStudent = useUpdateStudent();
  const [draft, setDraft] = useState<Draft>(() => toDraft(student));
  const [nameError, setNameError] = useState<string | null>(null);
  const wasOpen = useRef(false);

  // Reload the form only as the dialog opens, so a background refetch cannot
  // overwrite what the tutor is typing.
  useEffect(() => {
    if (open && !wasOpen.current) {
      setDraft(toDraft(student));
      setNameError(null);
    }
    wasOpen.current = open;
  }, [open, student]);

  const pending = createStudent.isPending || updateStudent.isPending;

  const save = async () => {
    const name = draft.name.trim();
    if (!name) {
      setNameError("A name is needed to add a student.");
      return;
    }
    const values = {
      name,
      level: draft.level.trim() || null,
      subjects: draft.subjects,
      notes: draft.notes.trim() || null,
    };
    try {
      if (student) {
        await updateStudent.mutateAsync({ id: student.id, patch: values });
        toast.success("Saved");
      } else {
        await createStudent.mutateAsync(values);
        toast.success("Added");
      }
      onClose();
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={student ? "Edit student" : "Add a student"}
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
            {student ? "Save changes" : "Add student"}
          </Button>
        </>
      }
    >
      <Field label="Name" required error={nameError}>
        <Input
          value={draft.name}
          autoFocus
          onChange={(event) => {
            setDraft((current) => ({ ...current, name: event.target.value }));
            setNameError(null);
          }}
        />
      </Field>
      <Field label="Level" help="Year group, exam board or grade.">
        <Input
          value={draft.level}
          onChange={(event) => {
            setDraft((current) => ({ ...current, level: event.target.value }));
          }}
        />
      </Field>
      <Field label="Subjects" help="Press Enter after each subject.">
        <TagInput
          value={draft.subjects}
          onChange={(subjects) => {
            setDraft((current) => ({ ...current, subjects }));
          }}
          placeholder="Maths"
        />
      </Field>
      <Field label="Notes">
        <Textarea
          value={draft.notes}
          onChange={(event) => {
            setDraft((current) => ({ ...current, notes: event.target.value }));
          }}
        />
      </Field>
    </Dialog>
  );
}
