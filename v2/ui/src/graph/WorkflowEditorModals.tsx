import type { OpEntry, Workflow, WorkflowLayout } from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";
import { RunInputsForm } from "../components/RunInputsForm";
import { ArtifactPreviewDialog } from "../previewers/ArtifactPreviewDialog";
import { DEFAULT_STAGE_ID, getOrderedStageIds } from "./layout";
import { prepareWorkflowForSave, toSnakeCaseId } from "./mutations";
import type { ArtifactPreviewTarget } from "./NodeInspector";
import {
  QuickConnectPopover,
  type QuickConnectDropData,
} from "./QuickConnectPopover";

export interface WorkflowEditorModalsProps {
  workflowPath: string;
  workflow: Workflow | null;
  layout: WorkflowLayout | null;
  ops: ReadonlyArray<OpEntry>;
  opsMap: Record<string, OpEntry>;
  showUnsavedRunConfirm: boolean;
  onCloseUnsavedRunConfirm: () => void;
  onRunWithoutSaving: () => void;
  onSaveAndRun: () => Promise<void>;
  showRunModal: boolean;
  runWithoutSaving: boolean;
  onCloseRunModal: () => void;
  onRunStarted: (newRunId: string) => void;
  previewTarget: ArtifactPreviewTarget | null;
  onClosePreview: () => void;
  showAddStageModal: boolean;
  newStageModalTitle: string;
  newStageModalRequireApproval: boolean;
  onChangeNewStageTitle: (title: string) => void;
  onChangeNewStageRequireApproval: (req: boolean) => void;
  onCloseAddStageModal: () => void;
  onCreateStage: (
    slug: string,
    title: string,
    options: { requireApproval: boolean },
  ) => void;
  stageToDelete: string | null;
  deleteStageChoice: "reassign" | "delete";
  onChangeDeleteStageChoice: (choice: "reassign" | "delete") => void;
  onCloseDeleteStage: () => void;
  onConfirmDeleteStage: () => void;
  quickConnectData: QuickConnectDropData | null;
  onQuickConnectSelect: (opId: string, portName: string) => void;
  onCloseQuickConnect: () => void;
}

export function WorkflowEditorModals({
  workflowPath,
  workflow,
  layout,
  ops,
  opsMap,
  showUnsavedRunConfirm,
  onCloseUnsavedRunConfirm,
  onRunWithoutSaving,
  onSaveAndRun,
  showRunModal,
  runWithoutSaving,
  onCloseRunModal,
  onRunStarted,
  previewTarget,
  onClosePreview,
  showAddStageModal,
  newStageModalTitle,
  newStageModalRequireApproval,
  onChangeNewStageTitle,
  onChangeNewStageRequireApproval,
  onCloseAddStageModal,
  onCreateStage,
  stageToDelete,
  deleteStageChoice,
  onChangeDeleteStageChoice,
  onCloseDeleteStage,
  onConfirmDeleteStage,
  quickConnectData,
  onQuickConnectSelect,
  onCloseQuickConnect,
}: WorkflowEditorModalsProps) {
  const reassignTargetStageId =
    workflow && stageToDelete
      ? getOrderedStageIds(workflow).find((sid) => sid !== stageToDelete) ??
        DEFAULT_STAGE_ID
      : DEFAULT_STAGE_ID;
  const reassignTargetTitle =
    workflow?.stages?.[reassignTargetStageId]?.title || reassignTargetStageId;

  return (
    <>
      {showUnsavedRunConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="unsaved-run-confirm-dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
          onClick={onCloseUnsavedRunConfirm}
        >
          <div
            className="w-full max-w-md rounded border border-[#404040] bg-[#242424] shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#3c3c3c] px-4 py-3">
              <div className="flex items-center gap-2">
                <FeatherIcon
                  name="alert-triangle"
                  size={16}
                  style={{ color: "var(--color-warning, #ffa726)" }}
                />
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Unsaved Changes
                </h3>
              </div>
              <button
                type="button"
                onClick={onCloseUnsavedRunConfirm}
                className="p-1 rounded hover:bg-[#3c3c3c]"
                style={{ color: "var(--text-secondary)" }}
              >
                <FeatherIcon name="x" size={14} />
              </button>
            </div>

            <div
              className="p-4 space-y-3 text-xs"
              style={{ color: "var(--text-secondary)" }}
            >
              <p>
                You have unsaved changes in this workflow. How would you like to
                launch the run?
              </p>
              <div className="rounded p-2.5 bg-[#1a1a1a] border border-[#333] space-y-1">
                <div>
                  <strong className="text-[var(--text-primary)]">
                    Save &amp; Run:
                  </strong>{" "}
                  Saves your current workflow to disk and executes it.
                </div>
                <div>
                  <strong className="text-[var(--text-primary)]">
                    Run Without Saving:
                  </strong>{" "}
                  Keeps the file on disk untouched, but executes your in-memory
                  editor workflow.
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-[#3c3c3c] bg-[#1e1e1e] px-4 py-2.5">
              <button
                type="button"
                data-testid="btn-cancel-unsaved-run"
                onClick={onCloseUnsavedRunConfirm}
                className="control-button h-7 px-3 text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="btn-run-without-saving"
                onClick={onRunWithoutSaving}
                className="control-button h-7 px-3 text-xs"
              >
                Run Without Saving
              </button>
              <button
                type="button"
                data-testid="btn-save-and-run"
                onClick={() => void onSaveAndRun()}
                className="control-button primary h-7 px-3 text-xs font-semibold"
              >
                Save &amp; Run
              </button>
            </div>
          </div>
        </div>
      )}

      {showRunModal && (
        <RunInputsForm
          workflowPath={workflowPath}
          asModal={true}
          inMemoryWorkflow={
            runWithoutSaving && workflow
              ? prepareWorkflowForSave(workflow)
              : undefined
          }
          inMemoryLayout={runWithoutSaving ? layout : undefined}
          opsMap={opsMap}
          onClose={onCloseRunModal}
          onRunStarted={onRunStarted}
        />
      )}

      {previewTarget && (
        <ArtifactPreviewDialog
          title={previewTarget.title}
          url={previewTarget.url}
          filename={previewTarget.filename}
          mediaType={previewTarget.mediaType}
          onClose={onClosePreview}
        />
      )}

      {/* Add Stage Modal */}
      {showAddStageModal && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="modal-add-stage"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={onCloseAddStageModal}
        >
          <div
            className="w-full max-w-sm rounded-lg p-5 shadow-xl space-y-4"
            style={{
              backgroundColor: "var(--bg-panel)",
              border: "1px solid var(--border-default)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 text-sm font-semibold">
              <FeatherIcon
                name="layers"
                size={16}
                style={{ color: "var(--color-primary)" }}
              />
              <span>Add Stage</span>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-[var(--text-secondary)] mb-1">
                  Stage Title
                </label>
                <input
                  type="text"
                  data-testid="modal-input-stage-title"
                  placeholder="e.g. Processing"
                  value={newStageModalTitle}
                  onChange={(e) => onChangeNewStageTitle(e.target.value)}
                  className="w-full px-2 py-1.5 text-xs rounded"
                  autoFocus
                />
              </div>

              <label className="flex items-start gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  data-testid="modal-checkbox-stage-gate"
                  checked={newStageModalRequireApproval}
                  onChange={(e) =>
                    onChangeNewStageRequireApproval(e.target.checked)
                  }
                  className="mt-0.5 rounded"
                />
                <div>
                  <span
                    className="font-semibold block"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Require approval (Stage Gate)
                  </span>
                  <span
                    className="text-[11px] block"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Pauses run execution before downstream stages begin.
                  </span>
                </div>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#3c3c3c]">
              <button
                type="button"
                onClick={onCloseAddStageModal}
                className="control-button"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="modal-btn-create-stage"
                disabled={!newStageModalTitle.trim()}
                onClick={() => {
                  const title = newStageModalTitle.trim();
                  const slug = toSnakeCaseId(title);
                  onCreateStage(slug, title, {
                    requireApproval: newStageModalRequireApproval,
                  });
                  onCloseAddStageModal();
                }}
                className="control-button primary"
              >
                Create Stage
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Stage with Operations Confirmation Modal */}
      {stageToDelete && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="modal-delete-stage"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={onCloseDeleteStage}
        >
          <div
            className="w-full max-w-md rounded-lg p-5 shadow-xl space-y-4"
            style={{
              backgroundColor: "var(--bg-panel)",
              border: "1px solid var(--border-default)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 text-sm font-semibold">
              <FeatherIcon
                name="alert-triangle"
                size={16}
                style={{ color: "var(--color-warning)" }}
              />
              <span>
                Delete Stage:{" "}
                {workflow?.stages?.[stageToDelete]?.title || stageToDelete}
              </span>
            </div>

            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              This stage contains{" "}
              <strong className="text-[var(--text-primary)]">
                {
                  Object.values(workflow?.nodes ?? {}).filter(
                    (n) => (n.stage || DEFAULT_STAGE_ID) === stageToDelete,
                  ).length
                }{" "}
                operations
              </strong>
              . Choose what to do with them:
            </p>

            <div className="space-y-2 text-xs">
              <label className="flex items-start gap-2 p-2.5 rounded bg-[#242424] border border-[#3c3c3c] cursor-pointer">
                <input
                  type="radio"
                  name="delete-stage-choice"
                  value="reassign"
                  checked={deleteStageChoice === "reassign"}
                  onChange={() => onChangeDeleteStageChoice("reassign")}
                  className="mt-0.5"
                />
                <div>
                  <span
                    className="font-semibold block"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Keep operations and move to {reassignTargetTitle} (
                    {reassignTargetStageId})
                  </span>
                  <span
                    className="text-[11px] block"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Operations and their connections will be retained in that
                    stage.
                  </span>
                </div>
              </label>

              <label className="flex items-start gap-2 p-2.5 rounded bg-[#242424] border border-[#3c3c3c] cursor-pointer">
                <input
                  type="radio"
                  name="delete-stage-choice"
                  value="delete"
                  checked={deleteStageChoice === "delete"}
                  onChange={() => onChangeDeleteStageChoice("delete")}
                  className="mt-0.5"
                />
                <div>
                  <span
                    className="font-semibold block"
                    style={{ color: "var(--color-error)" }}
                  >
                    Delete operations along with the stage
                  </span>
                  <span
                    className="text-[11px] block"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    All operations in this stage and their incoming/outgoing
                    wires will be deleted.
                  </span>
                </div>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#3c3c3c]">
              <button
                type="button"
                onClick={onCloseDeleteStage}
                className="control-button"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="btn-confirm-delete-stage"
                onClick={onConfirmDeleteStage}
                className="control-button danger"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {quickConnectData && (
        <QuickConnectPopover
          data={quickConnectData}
          ops={ops}
          onSelect={onQuickConnectSelect}
          onClose={onCloseQuickConnect}
        />
      )}
    </>
  );
}
