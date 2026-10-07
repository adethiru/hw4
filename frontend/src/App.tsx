import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import NavBar from "./components/NavBar.tsx";
import Footer from "./components/Footer.tsx";
import Ticker from "./components/Ticker.tsx";
import Home from "./pages/Home.tsx";
import Products from "./pages/Products.tsx";
import ProductDetail from "./pages/ProductDetail.tsx";
import ChatWidget from "./components/ChatWidget.tsx";
import About from "./pages/About.tsx";
import Login from "./pages/Login.tsx";
import Register from "./pages/Register.tsx";
import NotFound from "./pages/NotFound.tsx";
import { startReveal } from "./reveal.ts";

export default function App() {
  const location = useLocation();
  useEffect(() => startReveal(), []);

  return (
    <div className="app">
      <a href="#main" className="skip-link">Skip to content</a>
      <Ticker />
      <NavBar />
      {/* key on the path → a soft page-enter transition on every route change */}
      <main id="main" className="main page-enter" key={location.pathname}>
        <Routes location={location}>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
      <ChatWidget />
    </div>
  );
}
