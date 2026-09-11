import { useOutletContext } from "react-router-dom";

export interface StudentTabContext {
  studentId: string;
}

/** The student id from `/students/:id`, handed down by StudentDetailPage. */
export function useStudentTab(): StudentTabContext {
  return useOutletContext<StudentTabContext>();
}
