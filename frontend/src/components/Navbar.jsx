import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { fetchCurrentUser } from "../api/client";

const links = [
  { to: "/", label: "週報列表" },
  { to: "/search", label: "查詢" },
  { to: "/dashboard", label: "儀表板" },
  { to: "/settings", label: "設定" },
];

export default function Navbar() {
  const { pathname } = useLocation();
  const [user, setUser] = useState("");

  useEffect(() => {
    fetchCurrentUser()
      .then((data) => setUser(data?.user || ""))
      .catch(() => {});
  }, []);

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-6">
        <Link to="/" className="font-bold text-lg text-indigo-600 shrink-0">
          SRE Alert Tracker
        </Link>
        <div className="flex gap-1 flex-1">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                pathname === l.to
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
        {user && (
          <span className="text-xs text-gray-400 shrink-0">{user}</span>
        )}
      </div>
    </nav>
  );
}
