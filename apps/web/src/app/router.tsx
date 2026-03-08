import type { ReactElement } from "react";

import DashboardPage from "../pages/DashboardPage/DashboardPage";


type AppRoute = {
  path: string;
  element: ReactElement;
};


const routes: AppRoute[] = [
  {
    path: "/",
    element: <DashboardPage />,
  },
  {
    path: "/dashboard",
    element: <DashboardPage />,
  },
];


export function AppRouter(): ReactElement {
  const currentPath = window.location.pathname;
  const activeRoute = routes.find((route) => route.path === currentPath) ?? routes[0];

  return activeRoute.element;
}
