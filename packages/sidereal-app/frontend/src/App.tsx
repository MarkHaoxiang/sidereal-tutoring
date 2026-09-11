import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { StudentLayout } from "@/components/student/StudentLayout";
import { RequireAuth, RequireRole } from "@/lib/auth";

import { FeedbackDetailPage } from "./routes/FeedbackDetailPage";
import { HomePage } from "./routes/HomePage";
import { HomeworkDetailPage } from "./routes/HomeworkDetailPage";
import { LoginPage } from "./routes/LoginPage";
import { MaterialDetailPage } from "./routes/MaterialDetailPage";
import { PlanDetailPage } from "./routes/PlanDetailPage";
import { StudentDetailPage } from "./routes/StudentDetailPage";
import { StudentsListPage } from "./routes/StudentsListPage";
import { StudentFeedbackListPage } from "./routes/me/StudentFeedbackListPage";
import { StudentFeedbackPage } from "./routes/me/StudentFeedbackPage";
import { StudentHomePage } from "./routes/me/StudentHomePage";
import { StudentHomeworkListPage } from "./routes/me/StudentHomeworkListPage";
import { StudentHomeworkPage } from "./routes/me/StudentHomeworkPage";
import { StudentPlanPage } from "./routes/me/StudentPlanPage";
import { StudentSessionsPage } from "./routes/me/StudentSessionsPage";
import { FeedbackTab } from "./routes/student-tabs/FeedbackTab";
import { HomeworkTab } from "./routes/student-tabs/HomeworkTab";
import { MaterialTab } from "./routes/student-tabs/MaterialTab";
import { OverviewTab } from "./routes/student-tabs/OverviewTab";
import { PlansTab } from "./routes/student-tabs/PlansTab";
import { SessionsTab } from "./routes/student-tabs/SessionsTab";

// Two views behind one login. `RequireRole` decides which of them a caller belongs to,
// so the login page needs no branch of its own: it sends everyone to `/`, and a student
// is forwarded to `/me` from there.
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
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
