import { Routes, Route } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Recommendations } from "./pages/Recommendations";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="recommendations" element={<Recommendations />} />
      </Route>
    </Routes>
  );
}
