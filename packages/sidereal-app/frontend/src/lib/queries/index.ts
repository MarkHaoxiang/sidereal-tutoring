// How a page uses this layer: call a hook, render its `data`/`isLoading`/`isError`,
// and let mutations invalidate for you — no manual cache writes.
//   students  useStudents({status?}) · useStudent(id) · useCreateStudent · useUpdateStudent · useDeleteStudent
//   sessions  useSessions({studentId?,status?,from?,to?,sort?,limit?}) · useSession(id) · useSessionLinks(studentId) · useCreateSession · useUpdateSession · useDeleteSession
//   material  useDocuments({studentId?,status?,limit?}) · useDocument(id) · useCreateDocument · useUploadMaterialFile(file) · useRetryDocument · useDeleteDocument({id,fileId})
//   homework  useHomeworkList({studentId?,status?,limit?}) · useHomework(id) · useGeneratedQuestions(ids) · useUpdateHomework · useDeleteHomework
//   feedback  useFeedbackList({...}) · useFeedback(id) · useUpdateFeedback · useDeleteFeedback
//   plans     usePlans({...}) · usePlan(id) · useUpdatePlan · useDeletePlan
//   jobs      useCreateJob() then useJob(jobId) — it polls until succeeded/failed
// Documents and jobs poll themselves while unsettled (see pollWhile); every update
// takes `{id, patch}`, and failures are reported through `apiError(err)` from
// "@/lib/api" in a sonner toast.
export * from "./documents";
export * from "./feedback";
export * from "./homework";
export * from "./jobs";
export * from "./plans";
export * from "./poll";
export * from "./sessions";
export * from "./students";
