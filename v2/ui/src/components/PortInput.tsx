import { useEffect, useState } from "react";
import { uploadFile } from "../api/client";
import type { PortType } from "../api/types.gen";
import { FeatherIcon } from "./FeatherIcon";

export interface PortInputSpec {
  name: string;
  type: PortType | string;
  media?: string | null;
  options?: ReadonlyArray<string | number> | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  required?: boolean;
  default?: unknown;
  description?: string | null;
}

export interface PortInputProps {
  port: PortInputSpec;
  value: unknown;
  /** Optional controlled raw text (useful for form JSON validation on submit). */
  rawText?: string;
  readOnly?: boolean;
  onChange: (value: unknown, rawText?: string) => void;
  /** HTML id for label association. */
  id?: string;
  testId?: string;
  /** Compact inline styling (e.g., inside graph nodes). */
  compact?: boolean;
  /** Show quick-fill preset buttons below select dropdowns (default true in non-compact mode). */
  showPresets?: boolean;
  /** Allow toggling between raw JSON and structured list editor (default true in non-compact mode). */
  allowListEditor?: boolean;
  /** Show drag-and-drop upload zone for file inputs (used in run/stage forms). */
  fileDropZone?: boolean;
}

function getFileAccept(media?: string | null): string | undefined {
  if (!media) return undefined;
  switch (media) {
    case "audio":
      return "audio/*";
    case "image":
      return "image/*";
    case "video":
      return "video/*";
    case "text":
      return "text/*,.txt,.md,.json,.yaml,.yml,.csv";
    default:
      return undefined;
  }
}

export function PortInput({
  port,
  value,
  rawText,
  readOnly = false,
  onChange,
  id,
  testId,
  compact = false,
  showPresets = !compact,
  allowListEditor = !compact,
  fileDropZone = false,
}: PortInputProps) {
  const effectiveTestId = testId ?? `port-input-${port.name}`;
  const [multiline, setMultiline] = useState<boolean>(
    typeof value === "string" && value.includes("\n"),
  );
  const [jsonDraft, setJsonDraft] = useState<string>(() => {
    if (rawText !== undefined) return rawText;
    if (value !== undefined && value !== null && value !== "") {
      return typeof value === "string" ? value : JSON.stringify(value, null, 2);
    }
    if (port.default !== null && port.default !== undefined) {
      return typeof port.default === "string"
        ? port.default
        : JSON.stringify(port.default, null, 2);
    }
    return "";
  });
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

  const [jsonMode, setJsonMode] = useState<"raw" | "list">(() =>
    allowListEditor &&
    (Array.isArray(value) || (!value && Array.isArray(port.default)))
      ? "list"
      : "raw",
  );

  useEffect(() => {
    if (port.type === "json") {
      if (rawText !== undefined) {
        setJsonDraft(rawText);
      } else {
        setJsonDraft(
          value !== undefined && value !== null && value !== ""
            ? typeof value === "string"
              ? value
              : JSON.stringify(value, null, 2)
            : "",
        );
      }
      setJsonError(null);
    }
  }, [port.type, port.name, value, rawText]);

  const handleUpload = async (file: File) => {
    try {
      setUploading(true);
      setUploadError(null);
      setUploadedFileName(file.name);
      const res = await uploadFile(file);
      onChange(res.path, res.path);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  };

  // 1. Strict Literal[...] / Enum options -> dropdown (+ optional presets), NO custom value option
  if (port.options && port.options.length > 0) {
    const currentStr =
      value !== undefined && value !== null ? String(value) : "";
    const isUnknownLegacyValue =
      currentStr !== "" &&
      !port.options.some((opt) => String(opt) === currentStr);

    return (
      <div className={compact ? "w-full" : "space-y-1.5"}>
        <select
          id={id}
          data-testid={effectiveTestId}
          disabled={readOnly}
          value={currentStr}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") {
              onChange(undefined, "");
              return;
            }
            const matched = port.options?.find((opt) => String(opt) === raw);
            const nextVal = matched !== undefined ? matched : raw;
            onChange(nextVal, String(nextVal));
          }}
          className={
            compact ? "comfy-widget-select" : "w-full px-1.5 py-1 text-xs"
          }
        >
          <option value="">
            {port.default !== null && port.default !== undefined
              ? `(default: ${String(port.default)})`
              : "-- select --"}
          </option>
          {port.options.map((opt) => (
            <option key={String(opt)} value={String(opt)}>
              {String(opt)}
            </option>
          ))}
          {isUnknownLegacyValue && (
            <option value={currentStr} disabled>
              {currentStr} (invalid)
            </option>
          )}
        </select>

        {showPresets && (
          <div className="flex flex-wrap items-center gap-1">
            <span
              className="text-[10px]"
              style={{ color: "var(--text-tertiary)" }}
            >
              Presets:
            </span>
            {port.options.map((opt) => (
              <button
                key={String(opt)}
                type="button"
                disabled={readOnly}
                data-testid={`${effectiveTestId}-preset-${String(opt)}`}
                onClick={() => onChange(opt, String(opt))}
                className="px-1.5 py-0.5 text-[10px] rounded border hover:bg-white/10"
                style={{
                  borderColor:
                    String(opt) === currentStr
                      ? "var(--color-primary)"
                      : "var(--border-subtle)",
                  color:
                    String(opt) === currentStr
                      ? "var(--color-primary)"
                      : "inherit",
                }}
                title={`Quick-fill preset: ${String(opt)}`}
              >
                {String(opt)}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 2. Boolean -> checkbox toggle
  if (port.type === "bool") {
    const checked =
      typeof value === "boolean"
        ? value
        : value !== undefined && value !== ""
          ? Boolean(value)
          : port.default !== null && port.default !== undefined
            ? Boolean(port.default)
            : false;

    if (compact) {
      return (
        <input
          id={id}
          data-testid={effectiveTestId}
          type="checkbox"
          disabled={readOnly}
          checked={checked}
          onChange={(e) => onChange(e.target.checked, String(e.target.checked))}
          className="h-3.5 w-3.5 cursor-pointer"
        />
      );
    }

    return (
      <label className="flex items-center gap-2 text-xs cursor-pointer pt-0.5">
        <input
          id={id}
          data-testid={effectiveTestId}
          type="checkbox"
          disabled={readOnly}
          checked={checked}
          onChange={(e) => onChange(e.target.checked, String(e.target.checked))}
          className="h-3.5 w-3.5"
        />
        <span className="font-mono text-xs">{checked ? "true" : "false"}</span>
      </label>
    );
  }

  // 3. Numeric (int / float) with optional Range(min, max, step) slider
  if (port.type === "int" || port.type === "float") {
    const isInt = port.type === "int";
    const hasBounds =
      typeof port.min === "number" && typeof port.max === "number";
    const step =
      typeof port.step === "number" ? port.step : isInt ? 1 : 0.1;
    const displayVal =
      typeof value === "number"
        ? String(value)
        : rawText !== undefined
          ? rawText
          : "";
    const sliderVal =
      typeof value === "number"
        ? value
        : typeof port.default === "number"
          ? port.default
          : port.min ?? 0;

    const handleNumericInput = (raw: string) => {
      if (raw.trim() === "") {
        onChange(undefined, "");
        return;
      }
      const parsed = isInt ? parseInt(raw, 10) : parseFloat(raw);
      if (!Number.isNaN(parsed)) {
        onChange(parsed, raw);
      } else {
        onChange("", raw);
      }
    };

    if (compact) {
      return (
        <div className="flex items-center gap-1 min-w-0 flex-1 justify-end">
          {hasBounds && (
            <input
              data-testid={`${effectiveTestId}-slider`}
              type="range"
              disabled={readOnly}
              min={port.min ?? undefined}
              max={port.max ?? undefined}
              step={step}
              value={sliderVal}
              onChange={(e) => handleNumericInput(e.target.value)}
              className="w-16"
              style={{ accentColor: "var(--color-primary)" }}
            />
          )}
          <input
            id={id}
            data-testid={effectiveTestId}
            type="number"
            disabled={readOnly}
            min={port.min ?? undefined}
            max={port.max ?? undefined}
            step={
              typeof port.step === "number" ? port.step : isInt ? "1" : "any"
            }
            placeholder={
              port.default !== null && port.default !== undefined
                ? String(port.default)
                : isInt
                  ? "int"
                  : "float"
            }
            value={displayVal}
            onChange={(e) => handleNumericInput(e.target.value)}
            className="comfy-widget-input text-right font-mono"
          />
        </div>
      );
    }

    return (
      <div className="space-y-1">
        {hasBounds && (
          <div className="flex items-center gap-1.5">
            <input
              data-testid={`${effectiveTestId}-slider`}
              type="range"
              disabled={readOnly}
              min={port.min ?? undefined}
              max={port.max ?? undefined}
              step={step}
              value={sliderVal}
              onChange={(e) => handleNumericInput(e.target.value)}
              className="flex-1"
              style={{ accentColor: "var(--color-primary)" }}
            />
            <span
              className="w-10 text-right font-mono text-[11px]"
              style={{ color: "var(--text-secondary)" }}
            >
              {sliderVal}
            </span>
          </div>
        )}
        <input
          id={id}
          data-testid={effectiveTestId}
          type="number"
          disabled={readOnly}
          min={port.min ?? undefined}
          max={port.max ?? undefined}
          step={typeof port.step === "number" ? port.step : isInt ? "1" : "any"}
          placeholder={
            port.default !== null && port.default !== undefined
              ? `Default: ${String(port.default)}`
              : isInt
                ? "int"
                : "float"
          }
          value={displayVal}
          onChange={(e) => handleNumericInput(e.target.value)}
          className="w-full px-2 py-1 font-mono text-xs"
        />
      </div>
    );
  }

  // 4. JSON (dict or list)
  if (port.type === "json") {
    const listItems: Array<string> = Array.isArray(value)
      ? value.map((item) =>
          typeof item === "string" ? item : JSON.stringify(item),
        )
      : [];

    const handleListItemChange = (index: number, nextText: string) => {
      const nextList = [...listItems];
      nextList[index] = nextText;
      onChange(nextList, JSON.stringify(nextList));
    };

    const handleAddListItem = () => {
      const nextList = [...listItems, ""];
      onChange(nextList, JSON.stringify(nextList));
    };

    const handleRemoveListItem = (index: number) => {
      const nextList = listItems.filter((_, i) => i !== index);
      onChange(
        nextList.length > 0 ? nextList : undefined,
        nextList.length > 0 ? JSON.stringify(nextList) : "",
      );
    };

    if (allowListEditor && jsonMode === "list") {
      return (
        <div
          className="space-y-1.5"
          data-testid={`${effectiveTestId}-list-container`}
        >
          <div
            className="flex items-center justify-between text-[10px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            <span>List items ({listItems.length})</span>
            {!readOnly && (
              <button
                type="button"
                data-testid={`${effectiveTestId}-json-mode-toggle`}
                onClick={() => setJsonMode("raw")}
                className="hover:underline"
              >
                Raw JSON
              </button>
            )}
          </div>
          {listItems.length === 0 ? (
            <p
              className="text-[11px] italic"
              style={{ color: "var(--text-tertiary)" }}
            >
              Empty list
            </p>
          ) : (
            <div className="space-y-1 max-h-48 overflow-y-auto pr-0.5">
              {listItems.map((item, idx) => (
                <div key={idx} className="flex items-center gap-1">
                  <input
                    type="text"
                    disabled={readOnly}
                    data-testid={`${effectiveTestId}-list-item-${idx}`}
                    value={item}
                    placeholder={`Item ${idx + 1}`}
                    onChange={(e) => handleListItemChange(idx, e.target.value)}
                    className="flex-1 px-1.5 py-1 text-xs font-mono"
                  />
                  {!readOnly && (
                    <button
                      type="button"
                      disabled={readOnly}
                      data-testid={`${effectiveTestId}-list-remove-${idx}`}
                      onClick={() => handleRemoveListItem(idx)}
                      title="Remove item"
                      className="p-1 rounded hover:bg-[#3c3c3c] text-[var(--text-secondary)] hover:text-[var(--color-error)]"
                    >
                      <FeatherIcon name="x" size={11} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          {!readOnly && (
            <button
              type="button"
              data-testid={`${effectiveTestId}-list-add`}
              onClick={handleAddListItem}
              className="control-button h-5 min-h-5 px-2 text-[10px]"
            >
              <FeatherIcon name="plus" size={11} />
              <span>Add item</span>
            </button>
          )}
        </div>
      );
    }

    return (
      <div className="space-y-1 w-full">
        {allowListEditor && (
          <div
            className="flex items-center justify-between text-[10px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            <span>JSON</span>
            {!readOnly && (
              <button
                type="button"
                data-testid={`${effectiveTestId}-json-mode-toggle`}
                onClick={() => {
                  setJsonMode("list");
                  if (!Array.isArray(value)) {
                    onChange([], "[]");
                  }
                }}
                className="hover:underline"
              >
                List editor
              </button>
            )}
          </div>
        )}
        <textarea
          id={id}
          data-testid={effectiveTestId}
          rows={compact ? 2 : 3}
          disabled={readOnly}
          placeholder="Enter JSON object or array..."
          value={jsonDraft}
          onChange={(e) => {
            const raw = e.target.value;
            setJsonDraft(raw);
            if (raw.trim() === "") {
              setJsonError(null);
              onChange(undefined, "");
              return;
            }
            try {
              const parsed: unknown = JSON.parse(raw);
              if (typeof parsed !== "object" || parsed === null) {
                setJsonError("JSON port expects an object or array");
                onChange(raw, raw);
                return;
              }
              setJsonError(null);
              onChange(parsed, raw);
            } catch {
              setJsonError("Invalid JSON syntax");
              onChange(raw, raw);
            }
          }}
          className={
            compact
              ? "comfy-widget-textarea font-mono"
              : "w-full p-2 font-mono text-xs"
          }
        />
        {jsonError && (
          <p className="text-[10px]" style={{ color: "var(--color-error)" }}>
            {jsonError}
          </p>
        )}
      </div>
    );
  }

  // 5. File / Directory -> workspace-relative path + optional upload / dropzone
  if (port.type === "file" || port.type === "directory") {
    const strVal =
      typeof value === "string"
        ? value
        : rawText !== undefined
          ? rawText
          : "";

    if (fileDropZone && port.type === "file") {
      return (
        <div className="space-y-1.5">
          <div
            className="relative flex flex-col items-center justify-center rounded border-2 border-dashed p-3 text-center transition-colors"
            style={{
              borderColor: "var(--border-default)",
              backgroundColor: "var(--bg-app)",
            }}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (readOnly) return;
              const file = e.dataTransfer.files?.[0];
              if (file) {
                void handleUpload(file);
              }
            }}
          >
            <input
              type="file"
              disabled={readOnly}
              accept={getFileAccept(port.media)}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  void handleUpload(file);
                }
              }}
              className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
              aria-label={`Upload file for ${port.name}`}
            />
            {uploading ? (
              <span className="text-xs" style={{ color: "var(--color-primary)" }}>
                Uploading {uploadedFileName}...
              </span>
            ) : uploadedFileName && strVal ? (
              <div
                className="flex items-center gap-1.5 text-xs"
                style={{ color: "var(--color-status-success)" }}
              >
                <FeatherIcon name="check-circle" size={14} />
                <span>Uploaded: {uploadedFileName}</span>
                <span
                  className="font-mono text-[10px]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  ({strVal})
                </span>
              </div>
            ) : (
              <div
                className="flex flex-col items-center gap-1 text-xs"
                style={{ color: "var(--text-secondary)" }}
              >
                <FeatherIcon name="upload" size={16} />
                <span>Drop file here, or click to browse</span>
                {port.media && (
                  <span
                    className="text-[10px]"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    Accepts {port.media} files
                  </span>
                )}
              </div>
            )}
          </div>
          <input
            id={id}
            data-testid={effectiveTestId}
            type="text"
            disabled={readOnly}
            placeholder="Or enter path / upload path manually..."
            value={strVal}
            onChange={(e) =>
              onChange(
                e.target.value === "" ? undefined : e.target.value,
                e.target.value,
              )
            }
            className="w-full px-2 py-1 text-xs font-mono"
          />
          {uploadError && (
            <p className="text-[10px]" style={{ color: "var(--color-error)" }}>
              {uploadError}
            </p>
          )}
        </div>
      );
    }

    return (
      <div className={compact ? "w-full" : "space-y-1"}>
        <div className="flex items-center gap-1">
          <input
            id={id}
            data-testid={effectiveTestId}
            type="text"
            disabled={readOnly}
            placeholder={
              port.default !== null && port.default !== undefined
                ? String(port.default)
                : `${port.type} path...`
            }
            value={strVal}
            onChange={(e) =>
              onChange(
                e.target.value === "" ? undefined : e.target.value,
                e.target.value,
              )
            }
            className={
              compact
                ? "comfy-widget-input font-mono"
                : "min-w-0 flex-1 px-1.5 py-1 font-mono text-xs"
            }
          />
          {!readOnly && !compact && port.type === "file" && (
            <label
              className="control-button h-6 min-h-6 px-1.5 text-[11px]"
              title="Upload file"
            >
              <FeatherIcon name="upload" size={11} />
              <span>{uploading ? "..." : "Upload"}</span>
              <input
                type="file"
                accept={getFileAccept(port.media)}
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    void handleUpload(file);
                  }
                }}
              />
            </label>
          )}
        </div>
        {uploadError && (
          <p className="text-[10px]" style={{ color: "var(--color-error)" }}>
            {uploadError}
          </p>
        )}
      </div>
    );
  }

  // 6. String (single-line or multiline/code toggle)
  const strVal =
    typeof value === "string"
      ? value
      : rawText !== undefined
        ? rawText
        : "";
  const placeholder =
    port.default !== null && port.default !== undefined
      ? compact
        ? String(port.default)
        : `Default: ${String(port.default)}`
      : compact
        ? port.name
        : "Enter value...";

  if (compact) {
    return (
      <input
        id={id}
        data-testid={effectiveTestId}
        type="text"
        disabled={readOnly}
        placeholder={placeholder}
        value={strVal}
        onChange={(e) =>
          onChange(
            e.target.value === "" ? undefined : e.target.value,
            e.target.value,
          )
        }
        className="comfy-widget-input"
      />
    );
  }

  return (
    <div className="space-y-1">
      {multiline ? (
        <textarea
          id={id}
          data-testid={effectiveTestId}
          rows={3}
          disabled={readOnly}
          placeholder={placeholder}
          value={strVal}
          onChange={(e) =>
            onChange(
              e.target.value === "" ? undefined : e.target.value,
              e.target.value,
            )
          }
          className="w-full p-1.5 font-mono text-xs"
        />
      ) : (
        <input
          id={id}
          data-testid={effectiveTestId}
          type="text"
          disabled={readOnly}
          placeholder={placeholder}
          value={strVal}
          onChange={(e) =>
            onChange(
              e.target.value === "" ? undefined : e.target.value,
              e.target.value,
            )
          }
          className="w-full px-1.5 py-1 text-xs"
        />
      )}
      {!readOnly && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setMultiline((m) => !m)}
            className="text-[10px] hover:underline"
            style={{ color: "var(--text-tertiary)" }}
          >
            {multiline ? "Single line" : "Code / Multiline"}
          </button>
        </div>
      )}
    </div>
  );
}
