import { NavLink, Route, Routes } from "react-router-dom";
import RequestList from "./pages/RequestList";
import RequestDetail from "./pages/RequestDetail";
import LaunchMigration from "./pages/LaunchMigration";

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-mark" />
          <div>
            <h1>CI/CD Intelligence</h1>
            <p className="brand-sub">Migration Control</p>
          </div>
        </div>
        <div className="divider" />
        <p className="side-label">Workspace</p>
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <span className="dot" /> Active Requests
          </NavLink>
          <NavLink to="/launch" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <span className="dot" /> Launch Migration
          </NavLink>
        </nav>
        <div className="side-foot">
          <div className="role-card">
            <div className="k">Signed in as</div>
            <div className="v">Infra Director</div>
            <div className="k" style={{ marginTop: 8 }}>Approver ID</div>
            <div className="v mono" style={{ fontSize: ".78rem" }}>approver-456</div>
          </div>
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<RequestList />} />
          <Route path="/launch" element={<LaunchMigration />} />
          <Route path="/request/:id" element={<RequestDetail />} />
        </Routes>
      </main>
    </div>
  );
}
