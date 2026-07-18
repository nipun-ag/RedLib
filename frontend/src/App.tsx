import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { GatePage } from "@/pages/GatePage"
import { WorkspacePage } from "@/pages/WorkspacePage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<GatePage />} />
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/search.html" element={<Navigate to="/workspace" replace />} />
        <Route path="/index.html" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
