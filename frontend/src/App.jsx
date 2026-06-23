import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/Upload";
import Violations from "./pages/Violations";
import Reports from "./pages/Reports";
import LiveMonitor from "./pages/LiveMonitor";
import "./index.css";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/"           element={<Dashboard />} />
            <Route path="/upload"     element={<UploadPage />} />
            <Route path="/violations" element={<Violations />} />
            <Route path="/reports"    element={<Reports />} />
            <Route path="/live"       element={<LiveMonitor />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

