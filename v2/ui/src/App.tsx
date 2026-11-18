import type { ReactNode } from "react";
import { matchRoute, RouterProvider, useRouter } from "./router/Router";
import { Navbar } from "./components/Navbar";
import { RunList } from "./components/RunList";
import { WorkflowPicker } from "./components/WorkflowPicker";
import { RunDetail } from "./components/RunDetail";
import { RunInputsForm } from "./components/RunInputsForm";
import { WorkflowEditor } from "./graph/WorkflowEditor";

function AppShell() {
  const { currentPath } = useRouter();

  const editorMatch = matchRoute("/editor/:path*", currentPath);
  const isWide = editorMatch.matched && Boolean(editorMatch.params.path);

  let content: ReactNode;
  if (editorMatch.matched && editorMatch.params.path) {
    content = <WorkflowEditor workflowPath={editorMatch.params.path} />;
  } else {
    const runMatch = matchRoute("/runs/:id", currentPath);
    if (runMatch.matched && runMatch.params.id) {
      content = <RunDetail runId={runMatch.params.id} />;
    } else {
      const workflowMatch = matchRoute("/workflows/:path*", currentPath);
      if (workflowMatch.matched && workflowMatch.params.path) {
        content = <RunInputsForm workflowPath={workflowMatch.params.path} />;
      } else if (currentPath === "/workflows") {
        content = <WorkflowPicker />;
      } else {
        content = <RunList />;
      }
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar />
      <main
        className={`mx-auto w-full flex-1 px-6 py-8 ${
          isWide ? "max-w-[1600px]" : "max-w-6xl"
        }`}
      >
        {content}
      </main>
    </div>
  );
}

export function App() {
  return (
    <RouterProvider>
      <AppShell />
    </RouterProvider>
  );
}
