import { useEffect, useState } from "react";
import { fetchWorkflows } from "../api/client";
import type { WorkflowListItem } from "../api/types.gen";
import { Link, useRouter } from "../router/Router";
import {
  ControlButton,
  ControlPanel,
  ControlSeparator,
  SearchBar,
} from "./ControlPanel";
import { FeatherIcon } from "./FeatherIcon";
import { NewWorkflowModal } from "./NewWorkflowModal";

export function WorkflowPicker() {
  const { navigate } = useRouter();
  const [workflows, setWorkflows] = useState<ReadonlyArray<WorkflowListItem>>(
    [],
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");
  const [isNewModalOpen, setIsNewModalOpen] = useState<boolean>(false);

  const loadWorkflows = async () => {
    try {
      setLoading(true);
      setError(null);
      const items = await fetchWorkflows();
      setWorkflows(items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadWorkflows();
  }, []);

  const filtered = workflows.filter((wf) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      wf.name.toLowerCase().includes(q) || wf.path.toLowerCase().includes(q)
    );
  });

  return (
    <div className="ListPage">
      <ControlPanel>
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Search workflows by name or file path..."
          className="w-80"
        />
        <ControlSeparator />
        <ControlButton
          icon="plus"
          text="New Workflow"
          variant="primary"
          data-testid="btn-new-workflow"
          onClick={() => setIsNewModalOpen(true)}
        />
        <ControlButton
          icon="refresh-cw"
          text="Refresh"
          onClick={() => void loadWorkflows()}
        />
      </ControlPanel>

      {error && (
        <div
          role="alert"
          className="m-2 rounded border px-3 py-2 text-xs"
          style={{
            borderColor: "var(--color-error)",
            backgroundColor: "rgba(244, 67, 54, 0.15)",
            color: "#ff8a80",
          }}
        >
          {error}
        </div>
      )}

      <div className="list">
        <div className="list-header workflow-list-grid">
          <div className="list-field">Title</div>
          <div className="list-field">Path</div>
          <div className="list-field">Stages</div>
          <div className="list-field text-right">Actions</div>
        </div>

        {loading ? (
          <div
            className="p-8 text-center text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            Loading workflows...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-10 text-center">
            <p
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              No workflows found
            </p>
            <p
              className="mt-1 text-xs"
              style={{ color: "var(--text-tertiary)" }}
            >
              {workflows.length === 0
                ? "No workflows found in `workflows/` or `examples/workflows/`."
                : "No workflows matched your search."}
            </p>
          </div>
        ) : (
          filtered.map((wf) => (
            <Link
              key={wf.path}
              to={`/editor/${wf.path}?view=stepper`}
              data-testid={`workflow-card-${wf.path}`}
              className="list-row workflow-list-grid"
            >
              <div className="list-field flex items-center gap-2 font-semibold">
                <FeatherIcon
                  name="git-branch"
                  size={15}
                  style={{ color: "var(--color-primary)" }}
                />
                <span>{wf.name}</span>
              </div>

              <div
                className="list-field font-mono text-xs"
                style={{ color: "var(--text-secondary)" }}
              >
                {wf.path}
              </div>

              <div className="list-field">
                <span className="status-badge READY">
                  {wf.stage_count} {wf.stage_count === 1 ? "stage" : "stages"}
                </span>
              </div>

              <div
                className="flex items-center justify-end gap-1.5"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                }}
              >
                <ControlButton
                  icon="grid"
                  text="Graph"
                  data-testid={`edit-workflow-${wf.path}`}
                  onClick={() => navigate(`/editor/${wf.path}?view=graph`)}
                />
                <ControlButton
                  icon="play"
                  text="Run"
                  variant="primary"
                  onClick={() => navigate(`/workflows/${wf.path}`)}
                />
              </div>
            </Link>
          ))
        )}
      </div>

      <NewWorkflowModal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        existingPaths={workflows.map((wf) => wf.path)}
      />
    </div>
  );
}
