import { Link, useRouter } from "../router/Router";
import { FeatherIcon } from "./FeatherIcon";

export function Navbar() {
  const { currentPath } = useRouter();

  const isWorkflowsActive =
    currentPath === "/" ||
    currentPath.startsWith("/workflows") ||
    currentPath.startsWith("/editor");
  const isRunsActive = currentPath.startsWith("/runs");

  return (
    <header className="Header">
      <div className="header-left">
        <Link to="/workflows" className="logo">
          <img src="/logo.png" alt="PLynx" className="icon" />
          <span className="sr-only">PLynx</span>
        </Link>

        <nav className="Navigation" aria-label="Main navigation">
          <div className="NavigationItems">
            <span className="separator" />
            <Link
              to="/workflows"
              className={`Item ${isWorkflowsActive ? "active" : ""}`}
            >
              <FeatherIcon name="grid" size={14} />
              <span>Workflows</span>
            </Link>
            <span className="separator" />
            <Link
              to="/runs"
              className={`Item ${isRunsActive ? "active" : ""}`}
            >
              <FeatherIcon name="activity" size={14} />
              <span>Runs</span>
            </Link>
            <span className="separator" />
          </div>
        </nav>
      </div>

      <div className="flex items-center gap-3 pr-2 text-xs">
        <span
          className="font-mono text-[11px]"
          style={{ color: "var(--text-tertiary)" }}
        >
          v2.0.0
        </span>
      </div>
    </header>
  );
}
