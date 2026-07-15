import { Navigate, Route, Routes } from "react-router-dom";
import Gate from "./pages/Gate";
import Workspace from "./pages/Workspace";

const GATE_STORAGE_KEY = "redlib.researchGateAcknowledged";

function GateIndexRedirect() {
  const isAcknowledged =
    typeof window !== "undefined" &&
    window.localStorage.getItem(GATE_STORAGE_KEY) === "true";

  return isAcknowledged ? <Navigate to="/workspace" replace /> : <Gate />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<GateIndexRedirect />} />
      <Route path="/workspace" element={<Workspace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
