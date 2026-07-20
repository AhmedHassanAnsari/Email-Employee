// src/components/Dashboard.tsx
import React from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navigation = [
  { name: "Inbox", path: "/inbox" },
  { name: "Approval", path: "/approval" },
  { name: "Done", path: "/done" },
];

const Dashboard: React.FC = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-background text-white">
      {/* Sidebar */}
      <aside className="w-64 p-4 bg-card glass flex flex-col">
        <h2 className="text-2xl font-bold mb-6">Email Employee</h2>
        <nav className="flex-1 space-y-2">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                `block px-3 py-2 rounded ${isActive ? "bg-primary text-white" : "text-gray-300 hover:bg-primary/20"}`
              }
            >
              {item.name}
            </NavLink>
          ))}
        </nav>
        <button className="mt-4 btn-secondary glass" onClick={handleLogout}>
          Logout
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
};

export default Dashboard;
