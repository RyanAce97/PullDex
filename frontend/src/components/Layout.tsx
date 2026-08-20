import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./ErrorBoundary";

interface NavItem {
  to: string;
  label: string;
  children?: { to: string; label: string }[];
}

const navItems: NavItem[] = [
  { to: "/", label: "Dashboard" },
  {
    to: "/collection",
    label: "Collection",
    children: [
      { to: "/collection", label: "Collection" },
      { to: "/add", label: "+ Add Cards" },
      { to: "/binder", label: "Binder" },
      { to: "/pokedex", label: "Pokédex" },
    ],
  },
  {
    to: "/recommendations",
    label: "Recommendations",
    children: [
      { to: "/recommendations", label: "Recommendations" },
      { to: "/sets", label: "Sets" },
    ],
  },
  { to: "/settings", label: "Settings" },
];

// Paths that should highlight a parent nav item
const childPathMap: Record<string, string> = {
  "/add": "/collection",
  "/binder": "/collection",
  "/pokedex": "/collection",
  "/sets": "/recommendations",
};

export function Layout() {
  const location = useLocation();

  function isNavActive(item: NavItem): boolean {
    const path = location.pathname;
    if (path === item.to) return true;
    // Check if current path is a child of this item
    if (item.children) {
      for (const child of item.children) {
        if (path === child.to || path.startsWith(child.to + "/")) return true;
      }
    }
    // Check childPathMap
    const parentPath = childPathMap[path] || childPathMap[path.split("/").slice(0, 2).join("/")];
    if (parentPath === item.to) return true;
    // Handle /pokedex/:id
    if (path.startsWith("/pokedex/") && item.to === "/collection") return true;
    if (path.startsWith("/recommendations/") && item.to === "/recommendations") return true;
    return false;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm relative z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <h1 className="text-xl font-bold text-indigo-600">PullDex</h1>
            <nav className="flex gap-1">
              {navItems.map((item) => (
                <NavDropdown key={item.to} item={item} isActive={isNavActive(item)} />
              ))}
            </nav>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  );
}

function NavDropdown({ item, isActive }: { item: NavItem; isActive: boolean }) {
  if (!item.children) {
    return (
      <NavLink
        to={item.to}
        className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
          isActive
            ? "bg-indigo-100 text-indigo-700"
            : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
        }`}
      >
        {item.label}
      </NavLink>
    );
  }

  return (
    <div className="relative group">
      <NavLink
        to={item.to}
        className={`px-3 py-2 rounded-md text-sm font-medium transition-colors inline-flex items-center gap-1 ${
          isActive
            ? "bg-indigo-100 text-indigo-700"
            : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
        }`}
      >
        {item.label}
        <svg className="w-3 h-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </NavLink>

      {/* Dropdown */}
      <div className="absolute left-0 top-full pt-1 hidden group-hover:block">
        <div className="bg-white rounded-lg border border-gray-200 shadow-lg py-1 min-w-[160px]">
          {item.children.map((child) => (
            <NavLink
              key={child.to}
              to={child.to}
              className={({ isActive: childActive }) =>
                `block px-4 py-2 text-sm transition-colors ${
                  childActive
                    ? "bg-indigo-50 text-indigo-700 font-medium"
                    : "text-gray-700 hover:bg-gray-50"
                }`
              }
            >
              {child.label}
            </NavLink>
          ))}
        </div>
      </div>
    </div>
  );
}
