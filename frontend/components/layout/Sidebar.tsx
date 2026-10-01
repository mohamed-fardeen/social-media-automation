"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGrid,
  PenLine,
  Cpu,
  Library,
  Compass,
  Calendar,
  BarChart3,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Command Center", icon: LayoutGrid, hint: "01" },
  { href: "/studio", label: "Content Studio", icon: PenLine, hint: "02" },
  { href: "/agents", label: "AI Agents", icon: Cpu, hint: "03" },
  { href: "/knowledge", label: "Knowledge Base", icon: Library, hint: "04" },
  { href: "/research", label: "Research", icon: Compass, hint: "05" },
  { href: "/calendar", label: "Content Calendar", icon: Calendar, hint: "06" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, hint: "07" },
  { href: "/settings", label: "Settings", icon: Settings, hint: "08" },
];

export function Sidebar() {
  const pathname = usePathname() ?? "/";
  return (
    <aside className="w-[228px] shrink-0 border-r border-ink-600 bg-ink-900/60 flex flex-col h-full">
      {/* Brand */}
      <div className="px-4 py-5 border-b border-ink-600">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="relative grid h-7 w-7 place-items-center rounded-md bg-sodium-500 text-ink-950">
            <span className="absolute inset-0 rounded-md bg-sodium-500/20 blur-md opacity-0 group-hover:opacity-100 transition-opacity" />
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor">
              <path d="M2 2h2v12H2zm5 0h2v12H7zm5 0h2v12h-2z" opacity="0.85" />
            </svg>
          </span>
          <div className="leading-tight">
            <div className="font-display text-[15px] font-semibold tracking-tightest text-ink-50">
              Kelvin6k
            </div>
            <div className="font-mono text-2xs uppercase tracking-wider text-ink-300">
              AI Social Engine
            </div>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3">
        <ul className="space-y-0.5">
          {nav.map((item) => {
            const isActive =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors",
                    isActive
                      ? "text-ink-50 bg-ink-800"
                      : "text-ink-200 hover:text-ink-50 hover:bg-ink-850",
                  )}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[2px] rounded-r bg-sodium-500" />
                  )}
                  <Icon className={cn("h-4 w-4", isActive ? "text-sodium-500" : "text-ink-300")} />
                  <span className="flex-1 truncate">{item.label}</span>
                  <span className="font-mono text-2xs text-ink-400 group-hover:text-ink-300">
                    {item.hint}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
