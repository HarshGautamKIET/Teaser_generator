import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
// Oripio token layer first, then the app's composition on top of it.
import "@ds/styles.css";
import "./styles.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element not found");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
