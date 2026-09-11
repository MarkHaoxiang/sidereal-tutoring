import { feedbackKeys, homeworkKeys, planKeys } from "@/lib/queries";
import type { GenerationJobKind } from "@/lib/schema";

export interface ArtefactKindCopy {
  /** The button and dialog wording, in the tutor's words. */
  generateLabel: string;
  instructionsPlaceholder: string;
  /** Plans are generated for a period; homework and feedback are not. */
  hasPeriod: boolean;
  /** The `/students/:id/<route>/:artefactId` segment the artefact lives at. */
  route: string;
  listKey: readonly unknown[];
}

export const ARTEFACT_KINDS: Record<GenerationJobKind, ArtefactKindCopy> = {
  homework: {
    generateLabel: "Generate homework",
    instructionsPlaceholder: "Six questions on quadratic equations, easiest first, with the answers.",
    hasPeriod: false,
    route: "homework",
    listKey: homeworkKeys.all,
  },
  feedback: {
    generateLabel: "Generate feedback",
    instructionsPlaceholder: "A short note for the parents: what went well today, and what to practise.",
    hasPeriod: false,
    route: "feedback",
    listKey: feedbackKeys.all,
  },
  plan: {
    generateLabel: "Generate a study plan",
    instructionsPlaceholder: "Four weeks to the mock exam, two hours a week, algebra first.",
    hasPeriod: true,
    route: "plans",
    listKey: planKeys.all,
  },
};
