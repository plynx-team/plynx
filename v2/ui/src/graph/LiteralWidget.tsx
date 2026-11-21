import { useEffect, useState } from "react";
import { uploadFile } from "../api/client";
import type { InputPortSpec } from "../api/types.gen";
import { FeatherIcon } from "../components/FeatherIcon";

export interface LiteralWidgetProps {
  port: InputPortSpec;
  value: unknown;
  readOnly?: boolean;
  onChange: (value: unknown) => void;
  testIdPrefix?: string;
}

export function LiteralWidget({
  port,
  value,
  readOnly = false,
  onChange,
  testIdPrefix = "inspector-input",
}: LiteralWidgetProps) {
  const testId = `${testIdPrefix}-${port.name}`;
  const [multiline, setMultiline] = useState<boolean>(
    typeof value === "string" && value.includes("\n"),
  );
  const [jsonDraft, setJsonDraft] = useState<string>(() =>
    value !== undefined
      ? JSON.stringify(value, null, 2)
      : port.default !== null && port.default !== undefined
      ? JSON.stringify(port.default, null, 2)
      : "",
  );
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const isMatchingOption = Boolean(
    port.options?.some((opt) => String(opt) === String(value)),
  );
  const [isCustomOption, setIsCustomOption] = useState<boolean>(() =>
    Boolean(
      port.options &&
        port.options.length > 0 &&
        value !== undefined &&
        value !== null &&
        value !== "" &&
        !isMatchingOption,
    ),
  );

  const [jsonMode, setJsonMode] = useState<"raw" | "list">(() =>
    Array.isArray(value) || (!value && Array.isArray(port.default))
      ? "list"
      : "raw",
  );

  useEffect(() => {
    if (port.type === "json") {
      setJsonDraft(value !== undefined ? JSON.stringify(value, null, 2) : "");
      setJsonError(null);
    }
  }, [port.type, port.name, value]);

  // 1. Enum / Literal[...] options -> dropdown with custom value toggle + preset suggestions
  if (port.options && port.options.length > 0) {
    const currentStr =
      value !== undefined && value !== null ? String(value) : "";
    return (
      <div className="space-y-1.5">
        <div className="flex items-center gap-1">
          {isCustomOption ? (
            <input
              data-testid={testId}
              type="text"
              disabled={readOnly}
              placeholder={
                port.default !== null && port.default !== undefined
                  ? String(port.default)
                  : "Enter custom value..."
              }
              value={currentStr}
              onChange={(e) =>
                onChange(e.target.value === "" ? undefined : e.target.value)
              }
              className="w-full px-1.5 py-1 text-xs"
            />
          ) : (
            <select
              data-testid={testId}
              disabled={readOnly}
              value={currentStr}
              onChange={(e) => {
                const raw = e.target.value;
                if (raw === "__custom__") {
                  setIsCustomOption(true);
                  return;
                }
                if (raw === "") {
                  onChange(undefined);
                  return;
                }
                const matched = port.options?.find(
                  (opt) => String(opt) === raw,
                );
                onChange(matched !== undefined ? matched : raw);
              }}
              className="w-full px-1.5 py-1 text-xs"
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
              {!readOnly && (
                <option value="__custom__">Custom value...</option>
              )}
            </select>
          )}
        </div>
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
              data-testid={`${testId}-preset-${String(opt)}`}
              onClick={() => {
                onChange(opt);
                setIsCustomOption(false);
              }}
              className="px-1.5 py-0.5 text-[10px] rounded border hover:bg-[var(--bg-tertiary)]"
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
          {!readOnly && (
            <button
              type="button"
              data-testid={`${testId}-custom-toggle`}
              onClick={() => setIsCustomOption((c) => !c)}
              className="ml-auto text-[10px] hover:underline"
              style={{ color: "var(--text-tertiary)" }}
            >
              {isCustomOption ? "Select dropdown" : "Custom value"}
            </button>
          )}
        </div>
      </div>
    );
  }

  // 2. Boolean -> checkbox toggle
  if (port.type === "bool") {
    const checked =
      value !== undefined
        ? Boolean(value)
        : port.default !== null && port.default !== undefined
        ? Boolean(port.default)
        : false;
    return (
      <label className="flex items-center gap-1.5 text-xs cursor-pointer">
        <input
          data-testid={testId}
          type="checkbox"
          disabled={readOnly}
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
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
    const displayVal = typeof value === "number" ? String(value) : "";
    const sliderVal =
      typeof value === "number"
        ? value
        : typeof port.default === "number"
        ? port.default
        : port.min ?? 0;

    const handleNumericInput = (raw: string) => {
      if (raw.trim() === "") {
        onChange(undefined);
        return;
      }
      const parsed = isInt ? parseInt(raw, 10) : parseFloat(raw);
      if (!Number.isNaN(parsed)) {
        onChange(parsed);
      }
    };

    return (
      <div className="space-y-1">
        {hasBounds && (
          <div className="flex items-center gap-1.5">
            <input
              data-testid={`${testId}-slider`}
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
              className="w-8 text-right font-mono text-[11px]"
              style={{ color: "var(--text-secondary)" }}
            >
              {sliderVal}
            </span>
          </div>
        )}
        <input
          data-testid={testId}
          type="number"
          disabled={readOnly}
          min={port.min ?? undefined}
          max={port.max ?? undefined}
          step={typeof port.step === "number" ? port.step : isInt ? "1" : "any"}
          placeholder={
            port.default !== null && port.default !== undefined
              ? String(port.default)
              : isInt
              ? "int"
              : "float"
          }
          value={displayVal}
          onChange={(e) => handleNumericInput(e.target.value)}
          className="w-full px-1.5 py-1 font-mono text-xs"
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
      onChange(nextList);
    };

    const handleAddListItem = () => {
      const nextList = [...listItems, ""];
      onChange(nextList);
    };

    const handleRemoveListItem = (index: number) => {
      const nextList = listItems.filter((_, i) => i !== index);
      onChange(nextList.length > 0 ? nextList : undefined);
    };

    if (jsonMode === "list") {
      return (
        <div className="space-y-1.5" data-testid={`${testId}-list-container`}>
          <div
            className="flex items-center justify-between text-[10px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            <span>List items ({listItems.length})</span>
            {!readOnly && (
              <button
                type="button"
                data-testid={`${testId}-json-mode-toggle`}
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
                    data-testid={`${testId}-list-item-${idx}`}
                    value={item}
                    placeholder={`Item ${idx + 1}`}
                    onChange={(e) => handleListItemChange(idx, e.target.value)}
                    className="flex-1 px-1.5 py-1 text-xs font-mono"
                  />
                  {!readOnly && (
                    <button
                      type="button"
                      disabled={readOnly}
                      data-testid={`${testId}-list-remove-${idx}`}
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
              data-testid={`${testId}-list-add`}
              onClick={handleAddListItem}
              className="control-button !h-5 !min-h-5 !px-2 !text-[10px]"
            >
              <FeatherIcon name="plus" size={11} />
              <span>Add item</span>
            </button>
          )}
        </div>
      );
    }

    return (
      <div className="space-y-1">
        <div
          className="flex items-center justify-between text-[10px]"
          style={{ color: "var(--text-tertiary)" }}
        >
          <span>JSON</span>
          {!readOnly && (
            <button
              type="button"
              data-testid={`${testId}-json-mode-toggle`}
              onClick={() => {
                setJsonMode("list");
                if (!Array.isArray(value)) {
                  onChange([]);
                }
              }}
              className="hover:underline"
            >
              List editor
            </button>
          )}
        </div>
        <textarea
          data-testid={testId}
          rows={2}
          disabled={readOnly}
          placeholder='{"key": "value"} or ["a", "b"]'
          value={jsonDraft}
          onChange={(e) => {
            const raw = e.target.value;
            setJsonDraft(raw);
            if (raw.trim() === "") {
              setJsonError(null);
              onChange(undefined);
              return;
            }
            try {
              const parsed: unknown = JSON.parse(raw);
              if (typeof parsed !== "object" || parsed === null) {
                setJsonError("JSON port expects an object or array");
                return;
              }
              setJsonError(null);
              onChange(parsed);
            } catch {
              setJsonError("Invalid JSON syntax");
            }
          }}
          className="w-full p-1.5 font-mono text-xs"
        />
        {jsonError && (
          <p className="text-[10px]" style={{ color: "var(--color-error)" }}>
            {jsonError}
          </p>
        )}
      </div>
    );
  }

  // 5. File / Directory -> workspace-relative path + optional upload
  if (port.type === "file" || port.type === "directory") {
    const strVal = typeof value === "string" ? value : "";
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-1">
          <input
            data-testid={testId}
            type="text"
            disabled={readOnly}
            placeholder={
              port.default !== null && port.default !== undefined
                ? String(port.default)
                : `${port.type} path...`
            }
            value={strVal}
            onChange={(e) =>
              onChange(e.target.value === "" ? undefined : e.target.value)
            }
            className="min-w-0 flex-1 px-1.5 py-1 font-mono text-xs"
          />
          {!readOnly && port.type === "file" && (
            <label
              className="control-button !h-6 !min-h-6 !px-1.5 !text-[11px]"
              title="Upload file"
            >
              <FeatherIcon name="upload" size={11} />
              <span>{uploading ? "..." : "Upload"}</span>
              <input
                type="file"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  try {
                    setUploading(true);
                    setUploadError(null);
                    const res = await uploadFile(file);
                    onChange(res.path);
                  } catch (err: unknown) {
                    setUploadError(
                      err instanceof Error ? err.message : String(err),
                    );
                  } finally {
                    setUploading(false);
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
  const strVal = typeof value === "string" ? value : "";
  return (
    <div className="space-y-1">
      {multiline ? (
        <textarea
          data-testid={testId}
          rows={3}
          disabled={readOnly}
          placeholder={
            port.default !== null && port.default !== undefined
              ? String(port.default)
              : ""
          }
          value={strVal}
          onChange={(e) =>
            onChange(e.target.value === "" ? undefined : e.target.value)
          }
          className="w-full p-1.5 font-mono text-xs"
        />
      ) : (
        <input
          data-testid={testId}
          type="text"
          disabled={readOnly}
          placeholder={
            port.default !== null && port.default !== undefined
              ? String(port.default)
              : ""
          }
          value={strVal}
          onChange={(e) =>
            onChange(e.target.value === "" ? undefined : e.target.value)
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
