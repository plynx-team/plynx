import { Link, useRouter } from "../router/Router";

export function Navbar() {
  const { currentPath, navigate } = useRouter();

  const isRunsActive = currentPath === "/" || currentPath.startsWith("/runs");
  const isWorkflowsActive = currentPath.startsWith("/workflows");

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-8">
          <Link
            to="/runs"
            className="flex items-center gap-2.5 font-bold tracking-tight text-white hover:text-slate-200"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded bg-emerald-600 text-xs font-black text-white shadow">
              PL
            </span>
            <span className="text-base tracking-tight">PLynx</span>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold text-slate-400">
              v2.0
            </span>
          </Link>

          <nav className="flex items-center gap-1 text-sm font-medium">
            <Link
              to="/runs"
              className={`rounded-md px-3 py-1.5 transition-colors ${
                isRunsActive
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
              }`}
            >
              Runs
            </Link>
            <Link
              to="/workflows"
              className={`rounded-md px-3 py-1.5 transition-colors ${
                isWorkflowsActive
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
              }`}
            >
              Workflows
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate("/workflows")}
            className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600"
          >
            <span>+</span> New Run
          </button>
        </div>
      </div>
    </header>
  );
}
