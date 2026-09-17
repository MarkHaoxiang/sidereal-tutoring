import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button, Dialog, Field, Input, PdfView, Select } from "@/components/ui";
import { apiError } from "@/lib/api";
import { plainTextPreview } from "@/lib/typstText";
import { useStudents, useWorksheet } from "@/lib/queries";
import type { CanonicalQuestion } from "@/lib/schema";

import styles from "./papers.module.css";

export interface WorksheetDialogProps {
  open: boolean;
  onClose: () => void;
  paperId: string;
  paperTitle: string;
  /** The saved structure's questions — what the service will render from. */
  questions: CanonicalQuestion[];
}

function summary(question: CanonicalQuestion): string {
  return plainTextPreview(question.stem ?? question.parts?.[0]?.text ?? null, 100);
}

export function WorksheetDialog({ open, onClose, paperId, paperTitle, questions }: WorksheetDialogProps) {
  const students = useStudents();
  const worksheet = useWorksheet();
  const [chosen, setChosen] = useState<string[]>([]);
  const [studentId, setStudentId] = useState("");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pdfId, setPdfId] = useState<string | null>(null);
  const [homeworkId, setHomeworkId] = useState<string | null>(null);
  const navigate = useNavigate();

  const student = (students.data ?? []).find((candidate) => candidate.id === studentId) ?? null;
  const submitLabel = student ? "Set as homework" : "Make worksheet";

  const close = () => {
    setChosen([]);
    setStudentId("");
    setTitle("");
    setDue("");
    setError(null);
    setPdfId(null);
    setHomeworkId(null);
    onClose();
  };

  const toggle = (number: string) => {
    setError(null);
    setChosen((current) =>
      current.includes(number) ? current.filter((entry) => entry !== number) : [...current, number]
    );
  };

  const submit = async () => {
    if (chosen.length === 0) {
      setError("Tick at least one question.");
      return;
    }
    try {
      // In the order they are on the paper, whatever order they were ticked in.
      const numbers = questions.map((question) => question.number).filter((number) => chosen.includes(number));
      const result = await worksheet.mutateAsync({
        paperId,
        question_numbers: numbers,
        student_id: studentId || null,
        title: title.trim() || null,
        due: due || null,
      });
      setPdfId(result.pdf_file_id);
      setHomeworkId(result.homework_id ?? null);
    } catch (failure) {
      setError(apiError(failure));
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Make a worksheet"
      busy={worksheet.isPending}
      footer={
        pdfId ? (
          <>
            {homeworkId ? (
              <Button
                variant="primary"
                onClick={() => {
                  const to = `/students/${studentId}/homework/${homeworkId}`;
                  close();
                  void navigate(to);
                }}
              >
                Open the homework
              </Button>
            ) : null}
            <Button variant={homeworkId ? "ghost" : "primary"} onClick={close}>
              Done
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={close} disabled={worksheet.isPending}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={worksheet.isPending}
              disabled={questions.length === 0}
              onClick={() => {
                void submit();
              }}
            >
              {submitLabel}
            </Button>
          </>
        )
      }
    >
      {pdfId ? (
        <PdfView fileId={pdfId} fallbackName={`${title.trim() || paperTitle}.pdf`} />
      ) : (
        <>
          <p className={styles.note}>
            {student ? `Sets homework for ${student.name}.` : "Makes a PDF."}
          </p>

          <Field label="Questions" error={error}>
            {questions.length === 0 ? (
              <p className={styles.status}>No questions on this paper.</p>
            ) : (
              <div className={styles.picker}>
                {questions.map((question) => (
                  <label key={question.number} className={styles.choice}>
                    <input
                      type="checkbox"
                      checked={chosen.includes(question.number)}
                      onChange={() => {
                        toggle(question.number);
                      }}
                    />
                    <span className={styles.choiceNumber}>{question.number}</span>
                    <span className={styles.choiceText}>{summary(question)}</span>
                  </label>
                ))}
              </div>
            )}
          </Field>

          <Field label="For a student">
            <Select
              value={studentId}
              onChange={(event) => {
                setStudentId(event.target.value);
              }}
            >
              <option value="">Nobody — just the PDF</option>
              {(students.data ?? []).map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.name}
                </option>
              ))}
            </Select>
          </Field>

          <div className={styles.dates}>
            <Field label="Title" help="The paper's title is used if blank.">
              <Input
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value);
                }}
              />
            </Field>
            {student ? (
              <Field label="Due">
                <Input
                  type="date"
                  value={due}
                  onChange={(event) => {
                    setDue(event.target.value);
                  }}
                />
              </Field>
            ) : null}
          </div>
        </>
      )}
    </Dialog>
  );
}
