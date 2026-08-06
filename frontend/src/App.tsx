import { Routes, Route } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Pokedex } from "./pages/Pokedex";
import { RecommendationDetail } from "./pages/RecommendationDetail";
import { Recommendations } from "./pages/Recommendations";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="recommendations" element={<Recommendations />} />
        <Route path="recommendations/:setId" element={<RecommendationDetail />} />
        <Route path="pokedex" element={<Pokedex />} />
      </Route>
    </Routes>
  );
}
