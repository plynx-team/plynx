import { matchRoute, RouterProvider, useRouter } from "./router/Router";
import { Navbar } from "./components/Navbar";
import { RunList } from "./components/RunList";
import { WorkflowPicker } from "./components/WorkflowPicker";
import { RunDetail } from "./components/RunDetail";
import { RunInputsForm } from "./components/RunInputsForm";

function AppContent() {
  const { currentPath } = useRouter();

  // Match /runs/:id
  const runMatch = matchRoute("/runs/:id", currentPath);
  if (runMatch.matched && runMatch.params.id) {
    return <RunDetail runId={runMatch.params.id} />;
  }

  // Match /workflows/:path*
  const workflowMatch = matchRoute("/workflows/:path*", currentPath);
  if (workflowMatch.matched && workflowMatch.params.path) {
    return <RunInputsForm workflowPath={workflowMatch.params.path} />;
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
