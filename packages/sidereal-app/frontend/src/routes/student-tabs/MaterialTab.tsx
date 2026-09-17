import { useState } from "react";

import { AddMaterialDialog } from "@/components/material/AddMaterialDialog";
import { MaterialRow } from "@/components/material/MaterialRow";
import styles from "@/components/material/material.module.css";
import { Button, EmptyState, SkeletonRows } from "@/components/ui";
import { useDocuments } from "@/lib/queries";

import { useStudentTab } from "./context";

export function MaterialTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = useDocuments({ studentId });
  const [adding, setAdding] = useState(false);

  const open = () => {
    setAdding(true);
  };

  return (
    <div>
      {isLoading ? <SkeletonRows count={3} label="Loading material" /> : null}
      {isError ? <p className={styles.status}>Could not load the material.</p> : null}

      {data && data.length === 0 ? (
        <EmptyState
          message="No material yet."
          action={
            <Button variant="primary" onClick={open}>
              Add material
            </Button>
          }
        />
      ) : null}

      {data && data.length > 0 ? (
        <>
          <div className={styles.actions}>
            <Button variant="primary" onClick={open}>
              Add material
            </Button>
          </div>
          <ul className={styles.list}>
            {data.map((document) => (
              <MaterialRow
                key={document.id}
                document={document}
                to={`/students/${studentId}/material/${document.id}`}
              />
            ))}
          </ul>
        </>
      ) : null}

      <AddMaterialDialog
        open={adding}
        studentId={studentId}
        onClose={() => {
          setAdding(false);
        }}
      />
    </div>
  );
}
