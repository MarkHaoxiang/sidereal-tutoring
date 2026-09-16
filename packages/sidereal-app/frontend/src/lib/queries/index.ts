// How a page uses this layer: call a hook, render its `data`/`isLoading`/`isError`,
// and let mutations invalidate for you — no manual cache writes.
//   students  useStudents({status?}) · useStudent(id) · useCreateStudent · useUpdateStudent · useDeleteStudent
//   sessions  useSessions({studentId?,status?,from?,to?,sort?,limit?}) · useSession(id) · useSessionLinks(studentId) · useCreateSession · useUpdateSession · useDeleteSession
//   material  useDocuments({studentId?,status?,limit?}) · useLibraryDocuments({status?,limit?})
//             (the student-less rows every tutor shares) · useDocument(id) · useCreateDocument ·
//             useUploadMaterialFile(file) · useRetryDocument · useDeleteDocument({id,fileId})
//   papers    usePapers() (the library's papers) · usePaper(id) · useSavePaper({id,patch}) ·
//             useSetPaperStatus · useRenderPaper(id) · useWorksheet · useDeletePaper(id)
//             (it clears the paper's questions rows first)
//   homework  useHomeworkList({studentId?,status?,limit?}) · useHomework(id) · useGeneratedQuestions(ids) · useUpdateHomework · useDeleteHomework
//   feedback  useFeedbackList({...}) · useFeedback(id) · useUpdateFeedback · useDeleteFeedback
//   plans     usePlans({...}) · usePlan(id) · useUpdatePlan · useDeletePlan
//   topics    useTopics() (the whole tree) · useTopicUsage(id) · useCreateTopic ·
//             useUpdateTopic · useDeleteTopic · useTagDocument · useTagHomework
//   typeset   usePreviewTypst() (source → SVG pages) · useCompileHomework(id)
//   jobs      useCreateJob() then useJob(jobId) — it polls until succeeded/failed
//   logins    the student's sign-in, through the FastAPI app rather than Directus:
//             useCreateStudentLogin · useResetStudentPassword · useRemoveStudentLogin
//   admin     the whole practice, admin only: useAdminHealth · useTutors · useCreateTutor ·
//             useResetTutorPassword · useSetTutorStatus · useRemoveTutor · useAdminJobs ·
//             useTutorUsers · useReassignStudent
//   account   the signed-in user's own row, whoever they are: useSaveProfile ·
//             useSaveAvatar · useRemoveAvatar · useChangePassword · saveAppearance
//   me        the student view's own hooks, taking no student id (Directus filters to the
//             caller's own rows): useMyStudent · useMyHomeworkList · useMyHomework(id) ·
//             useMyFeedbackList · useMyFeedback(id) · useMyPlans · useMySessions ·
//             useSaveAnswers · useHandInHomework
// Documents and jobs poll themselves while unsettled (see pollWhile); every update
// takes `{id, patch}`, and failures are reported through `apiError(err)` from
// "@/lib/api" in a sonner toast.
export * from "./account";
export * from "./admin";
export * from "./documents";
export * from "./feedback";
export * from "./homework";
export * from "./jobs";
export * from "./logins";
export * from "./me";
export * from "./papers";
export * from "./plans";
export * from "./poll";
export * from "./sessions";
export * from "./students";
export * from "./topics";
export * from "./typeset";
