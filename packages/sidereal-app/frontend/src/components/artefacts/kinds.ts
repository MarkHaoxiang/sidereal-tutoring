import { feedbackKeys, homeworkKeys, planKeys } from "@/lib/queries";

// The generation kinds that belong to one student. `paper_extract` is a library
// operation, so it is a `GenerationJobKind` without being an artefact kind.
export type ArtefactKind = "homework" | "feedback" | "plan";

export interface ArtefactKindCopy {
  /** The button and dialog wording, in the tutor's words. */
  generateLabel: string;
  instructionsPlaceholder: string;
  /** Plans are generated for a period; homework and feedback are not. */
  hasPeriod: boolean;
  /** Homework alone can be written in Typst, so only it offers the choice. */
  hasFormat: boolean;
  /** Feedback alone is about a hand-in, so only it offers the homework to read. */
  hasHomework: boolean;
  /** The `/students/:id/<route>/:artefactId` segment the artefact lives at. */
  route: string;
  listKey: readonly unknown[];
}

export const ARTEFACT_KINDS: Record<ArtefactKind, ArtefactKindCopy> = {
  homework: {
    generateLabel: "Generate homework",
    instructionsPlaceholder: "Six questions on quadratic equations, easiest first, with the answers.",
    hasPeriod: false,
    hasFormat: true,
    hasHomework: false,
    route: "homework",
    listKey: homeworkKeys.all,
  },
  feedback: {
    generateLabel: "Generate feedback",
    instructionsPlaceholder: "Warm but honest; push on showing working.",
    hasPeriod: false,
    hasFormat: false,
    hasHomework: true,
    route: "feedback",
    listKey: feedbackKeys.all,
  },
  plan: {
    generateLabel: "Generate a study plan",
    instructionsPlaceholder: "Four weeks to the mock exam, two hours a week, algebra first.",
    hasPeriod: true,
    hasFormat: false,
    hasHomework: false,
    route: "plans",
    listKey: planKeys.all,
  },
};
