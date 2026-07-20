// src/App.tsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import SignIn from "./components/SignIn";
import Dashboard from "./components/Dashboard";
import Inbox from "./pages/Inbox";
import Approval from "./pages/Approval";
import Done from "./pages/Done";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { EventProvider } from "./context/EventContext";

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <EventProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<SignIn />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="inbox" replace />} />
              <Route path="inbox" element={<Inbox />} />
              <Route path="approval" element={<Approval />} />
              <Route path="done" element={<Done />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </EventProvider>
    </AuthProvider>
  );
};

export default App;
