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
    <div className="App">
      <Navbar />
      <main className="Content">{content}</main>
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
