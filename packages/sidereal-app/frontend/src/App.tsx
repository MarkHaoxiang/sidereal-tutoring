import { Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "@/components/admin/AdminLayout";
import { Layout } from "@/components/Layout";
import { StudentLayout } from "@/components/student/StudentLayout";
import { RequireAuth, RequireRole } from "@/lib/auth";

import { AccountPage } from "./routes/AccountPage";
import { FeedbackDetailPage } from "./routes/FeedbackDetailPage";
import { HomePage } from "./routes/HomePage";
import { HomeworkDetailPage } from "./routes/HomeworkDetailPage";
import { LibraryPage } from "./routes/LibraryPage";
import { LoginPage } from "./routes/LoginPage";
import { MaterialDetailPage } from "./routes/MaterialDetailPage";
import { PaperDetailPage } from "./routes/PaperDetailPage";
import { PapersPage } from "./routes/PapersPage";
import { PlanDetailPage } from "./routes/PlanDetailPage";
import { StudentDetailPage } from "./routes/StudentDetailPage";
import { StudentsListPage } from "./routes/StudentsListPage";
import { TopicsPage } from "./routes/TopicsPage";
import { AdminDashboardPage } from "./routes/admin/AdminDashboardPage";
import { AdminJobsPage } from "./routes/admin/AdminJobsPage";
import { AdminTutorsPage } from "./routes/admin/AdminTutorsPage";
import { StudentAccountPage } from "./routes/me/StudentAccountPage";
import { StudentFeedbackListPage } from "./routes/me/StudentFeedbackListPage";
import { StudentFeedbackPage } from "./routes/me/StudentFeedbackPage";
import { StudentHomePage } from "./routes/me/StudentHomePage";
import { StudentHomeworkListPage } from "./routes/me/StudentHomeworkListPage";
import { StudentHomeworkPage } from "./routes/me/StudentHomeworkPage";
import { StudentPlanPage } from "./routes/me/StudentPlanPage";
import { StudentSessionsPage } from "./routes/me/StudentSessionsPage";
import { PrintableTab } from "./routes/paper-tabs/PrintableTab";
import { QuestionsTab } from "./routes/paper-tabs/QuestionsTab";
import { SchemeTab } from "./routes/paper-tabs/SchemeTab";
import { SourceTab } from "./routes/paper-tabs/SourceTab";
import { FeedbackTab } from "./routes/student-tabs/FeedbackTab";
import { HomeworkTab } from "./routes/student-tabs/HomeworkTab";
import { MaterialTab } from "./routes/student-tabs/MaterialTab";
import { OverviewTab } from "./routes/student-tabs/OverviewTab";
import { PlansTab } from "./routes/student-tabs/PlansTab";
import { SessionsTab } from "./routes/student-tabs/SessionsTab";

// Three surfaces behind one login: the admin's, the tutor's, and the student's.
// `RequireRole` decides which of them a caller belongs to and forwards anyone who asks
// for one that is not theirs. An admin is admitted to the tutor app as well as `/admin`.
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <RequireRole role="tutor">
              <Layout />
            </RequireRole>
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="students" element={<StudentsListPage />} />
        <Route path="students/:id" element={<StudentDetailPage />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewTab />} />
          <Route path="sessions" element={<SessionsTab />} />
          <Route path="material" element={<MaterialTab />} />
          <Route path="homework" element={<HomeworkTab />} />
          <Route path="feedback" element={<FeedbackTab />} />
          <Route path="plans" element={<PlansTab />} />
        </Route>
        <Route path="students/:id/material/:docId" element={<MaterialDetailPage />} />
        <Route path="students/:id/homework/:artefactId" element={<HomeworkDetailPage />} />
        <Route path="students/:id/feedback/:artefactId" element={<FeedbackDetailPage />} />
        <Route path="students/:id/plans/:artefactId" element={<PlanDetailPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="library/papers" element={<PapersPage />} />
        <Route path="library/papers/:paperId" element={<PaperDetailPage />}>
          <Route index element={<Navigate to="questions" replace />} />
          <Route path="questions" element={<QuestionsTab />} />
          <Route path="scheme" element={<SchemeTab />} />
          <Route path="source" element={<SourceTab />} />
          <Route path="printable" element={<PrintableTab />} />
        </Route>
        <Route path="library/:docId" element={<MaterialDetailPage />} />
        <Route path="topics" element={<TopicsPage />} />
        <Route path="account" element={<AccountPage />} />
      </Route>
      <Route
        path="/admin"
        element={
          <RequireAuth>
            <RequireRole role="admin">
              <AdminLayout />
            </RequireRole>
          </RequireAuth>
        }
      >
        <Route index element={<AdminDashboardPage />} />
        <Route path="tutors" element={<AdminTutorsPage />} />
        <Route path="jobs" element={<AdminJobsPage />} />
        <Route path="topics" element={<TopicsPage />} />
      </Route>
      <Route
        path="/me"
        element={
          <RequireAuth>
            <RequireRole role="student">
              <StudentLayout />
            </RequireRole>
          </RequireAuth>
        }
      >
        <Route index element={<StudentHomePage />} />
        <Route path="homework" element={<StudentHomeworkListPage />} />
        <Route path="homework/:id" element={<StudentHomeworkPage />} />
        <Route path="feedback" element={<StudentFeedbackListPage />} />
        <Route path="feedback/:id" element={<StudentFeedbackPage />} />
        <Route path="plan" element={<StudentPlanPage />} />
        <Route path="sessions" element={<StudentSessionsPage />} />
        <Route path="account" element={<StudentAccountPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
