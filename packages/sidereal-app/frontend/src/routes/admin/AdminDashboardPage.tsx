import type { ReactNode } from "react";

import { Button, PageHeader, SkeletonRows } from "@/components/ui";
import { cx } from "@/lib/cx";
import { useAdminHealth } from "@/lib/queries";
import type { AdminHealth } from "@/lib/queries";

import pageStyles from "../page.module.css";
import styles from "./AdminDashboardPage.module.css";

type Licence = AdminHealth["directus"]["license"];

function licenceLine(licence: Licence): string {
  if (!licence) {
    return "Licence details unavailable";
  }
  if (licence.name && licence.status) {
    return `${licence.name} — licence ${licence.status}`;
  }
  if (licence.status) {
    return `Licence ${licence.status}`;
  }
  return licence.name ? `Licensed to ${licence.name}` : "Licence present";
}

function Tile({
  name,
  ok,
  children,
}: {
  name: string;
  /** Left out for a tile that reports configuration rather than a service that can be down. */
  ok?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={styles.tile}>
      <h2 className={styles.tileName}>{name}</h2>
      {ok === undefined ? null : (
        <p className={cx(styles.state, ok ? styles.ok : styles.degraded)}>
          <span className={styles.dot} aria-hidden="true" />
          {ok ? "Up" : "Not responding"}
        </p>
      )}
      <div className={styles.tileBody}>{children}</div>
    </section>
  );
}

export function AdminDashboardPage() {
  const { data: health, isLoading, isError, isFetching, refetch } = useAdminHealth();

  const counts: { label: string; value: number }[] = [
    { label: "Tutors", value: health?.counts.tutors ?? 0 },
    { label: "Students", value: health?.counts.students ?? 0 },
    { label: "Material", value: health?.counts.documents ?? 0 },
    { label: "Jobs running", value: health?.counts.jobs_running ?? 0 },
  ];

  return (
    <div>
      <PageHeader
        title="Dashboard"
        actions={
          <Button
            loading={isFetching}
            onClick={() => {
              void refetch();
            }}
          >
            Refresh
          </Button>
        }
      />

      {isLoading ? <SkeletonRows count={4} label="Checking the services" /> : null}
      {isError ? (
        <p className={pageStyles.status}>Could not reach the app.</p>
      ) : null}

      {health ? (
        <>
          <div className={styles.tiles}>
            <Tile name="Directus" ok={health.directus.ok}>
              <p className={styles.line}>
                {health.directus.version ? `Version ${health.directus.version}` : "Version unknown"}
              </p>
              <p className={styles.line}>{licenceLine(health.directus.license)}</p>
            </Tile>

            <Tile name="App" ok={health.api.ok}>
              <p className={styles.line}>Version {health.api.version}</p>
            </Tile>

            <Tile name="Typesetting" ok={health.typeset.ok}>
              <p className={styles.line}>{health.typeset.url}</p>
              {health.typeset.ok ? null : (
                <p className={styles.line}>No homework PDFs until it answers.</p>
              )}
            </Tile>

            <Tile name="Generation">
              <p className={styles.line}>
                {health.generation.backend === "fake" ? "Stand-in generator" : health.generation.backend}
              </p>
              <p className={styles.model}>{health.generation.model}</p>
              {health.generation.backend === "fake" ? (
                <p className={styles.line}>No model is called; generated work is placeholder text.</p>
              ) : null}
            </Tile>
          </div>

          <dl className={styles.counts}>
            {counts.map((count) => (
              <div key={count.label} className={styles.count}>
                <dd className={styles.countValue}>{count.value}</dd>
                <dt className={styles.countLabel}>{count.label}</dt>
              </div>
            ))}
          </dl>
        </>
      ) : null}
    </div>
  );
}
