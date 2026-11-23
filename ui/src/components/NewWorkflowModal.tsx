import { useEffect, useId, useState } from "react";
import { saveWorkflow } from "../api/client";
import type { WorkflowDocument } from "../api/types.gen";
import { useRouter } from "../router/Router";
import { FeatherIcon } from "./FeatherIcon";

export interface NewWorkflowModalProps {
  isOpen: boolean;
  onClose: () => void;
  existingPaths?: ReadonlyArray<string>;
  onCreated?: (path: string) => void;
}

function slugifyName(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function NewWorkflowModal({
  isOpen,
  onClose,
  existingPaths = [],
  onCreated,
}: NewWorkflowModalProps) {
  const { navigate } = useRouter();
  const titleId = useId();
  const [name, setName] = useState<string>("");
  const [path, setPath] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [pathManuallyEdited, setPathManuallyEdited] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setName("");
      setPath("");
      setDescription("");
      setPathManuallyEdited(false);
      setIsSubmitting(false);
      setError(null);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleNameChange = (val: string) => {
    setName(val);
    if (!pathManuallyEdited) {
      const slug = slugifyName(val);
      setPath(slug ? `workflows/${slug}.yaml` : "");
    }
  };

  const handlePathChange = (val: string) => {
    setPath(val);
    setPathManuallyEdited(true);
  };

  const normalizedPath = path.trim();
  const trimmedName = name.trim();

  let validationError: string | null = null;
  if (!trimmedName) {
    validationError = "Workflow name is required.";
  } else if (!normalizedPath) {
    validationError = "File path is required.";
  } else if (
    !normalizedPath.endsWith(".yaml") &&
    !normalizedPath.endsWith(".yml")
  ) {
    validationError = "File path must end with .yaml or .yml";
  } else if (normalizedPath.includes("..") || normalizedPath.startsWith("/")) {
    validationError = "File path must be a valid relative path within workspace.";
  } else if (
    existingPaths.some(
      (p) => p.toLowerCase() === normalizedPath.toLowerCase(),
    )
  ) {
    validationError = `A workflow at "${normalizedPath}" already exists.`;
  }

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (validationError || isSubmitting) return;

    try {
      setIsSubmitting(true);
      setError(null);

      const initialDoc: WorkflowDocument = {
        workflow: {
          version: 1,
          name: trimmedName,
          description: description.trim() || undefined,
          stages: {
            main: {
              title: "Main",
              require_approval: false,
            },
          },
          nodes: {},
        },
        layout: {
          schema: 1,
          nodes: {},
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      };

      await saveWorkflow(normalizedPath, initialDoc);
      onClose();
      if (onCreated) {
        onCreated(normalizedPath);
      } else {
        navigate(`/editor/${normalizedPath}`);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      data-testid="modal-new-workflow"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg p-5 shadow-xl space-y-4"
        style={{
          backgroundColor: "var(--bg-panel)",
          border: "1px solid var(--border-default)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <FeatherIcon
              name="plus-circle"
              size={18}
              style={{ color: "var(--color-primary)" }}
            />
            <span id={titleId}>Create New Workflow</span>
          </div>
          <button
            type="button"
            data-testid="btn-close-new-workflow-modal"
            aria-label="Close dialog"
            onClick={onClose}
            className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <FeatherIcon name="x" size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          {error && (
            <div
              role="alert"
              data-testid="new-workflow-error"
              className="rounded border px-3 py-2 text-xs"
              style={{
                borderColor: "var(--color-error)",
                backgroundColor: "rgba(244, 67, 54, 0.15)",
                color: "#ff8a80",
              }}
            >
              {error}
            </div>
          )}

          <div>
            <label className="block text-[var(--text-secondary)] mb-1 font-medium">
              Workflow Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              data-testid="input-new-workflow-name"
              placeholder="e.g. Image Classifier Pipeline"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border-default)] bg-[var(--bg-canvas)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--color-primary)]"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-[var(--text-secondary)] mb-1 font-medium">
              File Path <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              data-testid="input-new-workflow-path"
              placeholder="workflows/my_pipeline.yaml"
              value={path}
              onChange={(e) => handlePathChange(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border-default)] bg-[var(--bg-canvas)] text-[var(--text-primary)] font-mono focus:outline-none focus:border-[var(--color-primary)]"
            />
            <div className="mt-1 text-[11px] text-[var(--text-tertiary)]">
              Workflow YAML path relative to workspace root
            </div>
          </div>

          <div>
            <label className="block text-[var(--text-secondary)] mb-1 font-medium">
              Description <span className="text-[var(--text-tertiary)]">(optional)</span>
            </label>
            <textarea
              data-testid="input-new-workflow-description"
              placeholder="Brief summary of what this workflow does..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border-default)] bg-[var(--bg-canvas)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--color-primary)] resize-none"
            />
          </div>

          {validationError && (
            <div className="text-[11px] text-[var(--color-warning,orange)]">
              {validationError}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-default)]">
            <button
              type="button"
              data-testid="btn-cancel-new-workflow"
              onClick={onClose}
              className="px-3 py-1.5 rounded text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-button-hover)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="btn-submit-new-workflow"
              disabled={Boolean(validationError) || isSubmitting}
              className="px-3.5 py-1.5 rounded text-xs font-semibold text-white transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ backgroundColor: "var(--color-primary)" }}
            >
              {isSubmitting ? "Creating..." : "Create Workflow"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
