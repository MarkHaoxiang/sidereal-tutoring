import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { RequireAuth } from "@/lib/auth";

import { FeedbackDetailPage } from "./routes/FeedbackDetailPage";
import { HomePage } from "./routes/HomePage";
import { HomeworkDetailPage } from "./routes/HomeworkDetailPage";
import { LoginPage } from "./routes/LoginPage";
import { MaterialDetailPage } from "./routes/MaterialDetailPage";
import { PlanDetailPage } from "./routes/PlanDetailPage";
import { StudentDetailPage } from "./routes/StudentDetailPage";
import { StudentsListPage } from "./routes/StudentsListPage";
import { FeedbackTab } from "./routes/student-tabs/FeedbackTab";
import { HomeworkTab } from "./routes/student-tabs/HomeworkTab";
import { MaterialTab } from "./routes/student-tabs/MaterialTab";
import { OverviewTab } from "./routes/student-tabs/OverviewTab";
import { PlansTab } from "./routes/student-tabs/PlansTab";
import { SessionsTab } from "./routes/student-tabs/SessionsTab";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
