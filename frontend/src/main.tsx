import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

// Register PWA service worker
if ("serviceWorker" in navigator) {
  import("workbox-window").then(({ Workbox }) => {
    const wb = new Workbox("/sw.js");

    wb.addEventListener("installed", (event) => {
      if (event.isUpdate) {
        // New service worker installed, prompt user to refresh
        if (confirm("גרסה חדשה זמינה. לרענן?")) {
          window.location.reload();
        }
      }
    });

    wb.register().catch((err: unknown) => {
      console.warn("SW registration failed:", err);
    });
  }).catch(() => {
    // workbox-window not available, skip SW registration
  });
}
