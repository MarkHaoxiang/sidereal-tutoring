import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button, Dialog, Field, Select, Spinner } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useExtractMarkScheme, useLibraryDocuments } from "@/lib/queries";

import styles from "./papers.module.css";

export interface MarkSchemeDialogProps {
  open: boolean;
  onClose: () => void;
  paperId: string;
  /** Whether this paper already has a mark scheme — only the title and button wording change. */
  rerun: boolean;
}

function looksLikeAScheme(title: string | null): boolean {
  return title !== null && title.toLowerCase().includes("mark scheme");
}

/** The library, ready and student-less, with the obvious scheme (if any) picked first. */
export function MarkSchemeDialog({ open, onClose, paperId, rerun }: MarkSchemeDialogProps) {
  const library = useLibraryDocuments({ status: ["ready"] });
  const extract = useExtractMarkScheme();
  const [documentId, setDocumentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [primed, setPrimed] = useState(false);

  const documents = library.data ?? [];

  // Opening the dialog picks the obvious document; after that the tutor's choice stands,
  // however the query refetches underneath.
  useEffect(() => {
    if (!open) {
      setPrimed(false);
      return;
    }
    if (primed || library.isLoading) {
      return;
    }
    const guess = documents.find((row) => looksLikeAScheme(row.title));
    setDocumentId(guess?.id ?? "");
    setPrimed(true);
    // `documents` is derived from `library.data` every render; only its loading edge matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, primed, library.isLoading]);

  const close = () => {
    setError(null);
    onClose();
  };

  const submit = async () => {
    if (!documentId) {
      setError("Choose a document.");
      return;
    }
    try {
      await extract.mutateAsync({ paperId, document_id: documentId });
      toast.success("Extracted");
      close();
    } catch (failure) {
      setError(apiError(failure));
    }
  };

  const label = rerun ? "Re-extract mark scheme" : "Extract mark scheme";

  return (
    <Dialog
      open={open}
      onClose={close}
      title={label}
      busy={extract.isPending}
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={extract.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={extract.isPending}
            disabled={documents.length === 0}
            onClick={() => {
              void submit();
            }}
          >
            {label}
          </Button>
        </>
      }
    >
      <Field label="Mark scheme document" error={error}>
        {library.isLoading ? (
          <p className={styles.status}>
            <Spinner /> Loading the library…
          </p>
        ) : documents.length === 0 ? (
          <p className={styles.status}>The library is empty. Add the mark scheme on the Material tab.</p>
        ) : (
          <Select
            value={documentId}
            onChange={(event) => {
              setError(null);
              setDocumentId(event.target.value);
            }}
          >
            <option value="">Choose a document</option>
            {documents.map((row) => (
              <option key={row.id} value={row.id}>
                {row.title ?? "Untitled material"}
              </option>
            ))}
          </Select>
        )}
      </Field>
    </Dialog>
  );
}
