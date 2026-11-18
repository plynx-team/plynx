import { matchRoute, RouterProvider, useRouter } from "./router/Router";
import { Navbar } from "./components/Navbar";
import { RunList } from "./components/RunList";
import { WorkflowPicker } from "./components/WorkflowPicker";
import { RunDetail } from "./components/RunDetail";

function AppContent() {
  const { currentPath, navigate } = useRouter();

  // Match /runs/:id
  const runMatch = matchRoute("/runs/:id", currentPath);
  if (runMatch.matched && runMatch.params.id) {
    return <RunDetail runId={runMatch.params.id} />;
  }

  // Match /workflows/:path*
  const workflowMatch = matchRoute("/workflows/:path*", currentPath);
  if (workflowMatch.matched && workflowMatch.params.path) {
    const wfPath = workflowMatch.params.path;
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <button
            type="button"
            onClick={() => navigate("/workflows")}
            className="hover:text-slate-200"
          >
            &larr; Workflows
          </button>
          <span>/</span>
          <span className="font-mono text-slate-300">{wfPath}</span>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6">
          <h2 className="text-base font-semibold text-white">
            Workflow: {wfPath}
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Workflow configuration and inputs
          </p>
          <div className="mt-6 flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate("/workflows")}
              className="rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700"
            >
              Back to Workflows
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Match /workflows
  if (currentPath === "/workflows") {
    return <WorkflowPicker />;
  }

  // Default to /runs
  return <RunList />;
}

export function App() {
  return (
    <RouterProvider>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <Navbar />
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
          <AppContent />
        </main>
      </div>
    </RouterProvider>
  );
}
