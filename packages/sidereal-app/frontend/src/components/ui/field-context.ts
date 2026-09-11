import { createContext, useContext } from "react";

// The attributes a <Field> hands to whatever control it wraps. Every control in this
// folder spreads these before its own props, so a control inside a Field is labelled
// and described without the caller wiring ids by hand.
export interface FieldControlAttributes {
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

export const FieldContext = createContext<FieldControlAttributes | null>(null);

export function useFieldControl(): FieldControlAttributes {
  return useContext(FieldContext) ?? {};
}
