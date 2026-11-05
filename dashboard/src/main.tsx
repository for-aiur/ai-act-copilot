import React from "react";
import ReactDOM from "react-dom/client";
import App from "./Workbench";
import { AuthPage, CustomerDashboard, Onboarding, NewReview, PublicHome } from "./CustomerApp";
import "./styles.css";
import "./customer.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {location.pathname === "/workbench" ? <App /> :
      location.pathname === "/login" ? <AuthPage mode="login" /> :
      location.pathname === "/register" ? <AuthPage mode="register" /> :
      location.pathname === "/onboarding" ? <Onboarding /> :
      location.pathname === "/app/new" ? <NewReview /> :
      location.pathname.startsWith("/app") ? <CustomerDashboard /> : <PublicHome />}
  </React.StrictMode>,
);
