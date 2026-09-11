import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { RequireAuth } from "@/lib/auth";

import { LoginPage } from "./routes/LoginPage";
import { StudentDetailPage } from "./routes/StudentDetailPage";
import { StudentsListPage } from "./routes/StudentsListPage";

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
        <Route index element={<StudentsListPage />} />
        <Route path="students/:id" element={<StudentDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
