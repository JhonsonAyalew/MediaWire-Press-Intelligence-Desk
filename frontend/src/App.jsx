import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Database from "./pages/Database.jsx";
import ScrapeDesk from "./pages/ScrapeDesk.jsx";
import Assistant from "./pages/Assistant.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/database" element={<Database />} />
        <Route path="/scrape" element={<ScrapeDesk />} />
        <Route path="/assistant" element={<Assistant />} />
      </Routes>
    </Layout>
  );
}
