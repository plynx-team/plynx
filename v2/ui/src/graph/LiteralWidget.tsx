import { useEffect, useState } from "react";
import { uploadFile } from "../api/client";
import type { InputPortSpec } from "../api/types.gen";

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

  useEffect(() => {
    if (port.type === "json") {
      setJsonDraft(value !== undefined ? JSON.stringify(value, null, 2) : "");
      setJsonError(null);
    }
  }, [port.type, port.name, value]);

  // 1. Enum / Literal[...] options -> select dropdown
  if (port.options && port.options.length > 0) {
    const currentStr =
      value !== undefined && value !== null ? String(value) : "";
    return (
      <select
        data-testid={testId}
        disabled={readOnly}
        value={currentStr}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            onChange(undefined);
            return;
          }
          const matched = port.options?.find((opt) => String(opt) === raw);
          onChange(matched !== undefined ? matched : raw);
        }}
        className="w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
      >
        <option value="">
          {port.default !== null && port.default !== undefined
            ? `(default: ${String(port.default)})`
            : "-- select option --"}
        </option>
        {port.options.map((opt) => (
          <option key={String(opt)} value={String(opt)}>
            {String(opt)}
          </option>
        ))}
      </select>
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
      <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
        <input
          data-testid={testId}
          type="checkbox"
          disabled={readOnly}
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-emerald-500 disabled:opacity-60"
        />
        <span className="font-mono">{checked ? "true" : "false"}</span>
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
      typeof value === "number" ? String(value) : "";
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
      <div className="space-y-1.5">
        {hasBounds && (
          <div className="flex items-center gap-2">
            <input
              data-testid={`${testId}-slider`}
              type="range"
              disabled={readOnly}
              min={port.min ?? undefined}
              max={port.max ?? undefined}
              step={step}
              value={sliderVal}
              onChange={(e) => handleNumericInput(e.target.value)}
              className="flex-1 accent-emerald-500"
            />
            <span className="w-12 text-right font-mono text-[11px] text-slate-400">
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
              ? `Default: ${String(port.default)}`
              : isInt
              ? "Enter integer..."
              : "Enter number..."
          }
          value={displayVal}
          onChange={(e) => handleNumericInput(e.target.value)}
          className="w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
        />
      </div>
    );
  }

  // 4. JSON (dict or list)
  if (port.type === "json") {
    return (
      <div className="space-y-1">
        <textarea
          data-testid={testId}
          rows={3}
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
              if (
                typeof parsed !== "object" ||
                parsed === null
              ) {
                setJsonError("JSON port expects an object or array");
                return;
              }
              setJsonError(null);
              onChange(parsed);
            } catch {
              setJsonError("Invalid JSON syntax");
            }
          }}
          className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
        />
        {jsonError && (
          <p className="text-[10px] text-rose-400">{jsonError}</p>
        )}
      </div>
    );
  }

  // 5. File / Directory -> workspace-relative path + optional upload
  if (port.type === "file" || port.type === "directory") {
    const strVal = typeof value === "string" ? value : "";
    return (
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5">
          <input
            data-testid={testId}
            type="text"
            disabled={readOnly}
            placeholder={
              port.default !== null && port.default !== undefined
                ? `Default: ${String(port.default)}`
                : `Workspace-relative ${port.type} path...`
            }
            value={strVal}
            onChange={(e) =>
              onChange(e.target.value === "" ? undefined : e.target.value)
            }
            className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
          />
          {!readOnly && port.type === "file" && (
            <label className="shrink-0 cursor-pointer rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-[11px] font-medium text-slate-300 hover:bg-slate-800">
              {uploading ? "..." : "Upload"}
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
          <p className="text-[10px] text-rose-400">{uploadError}</p>
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
              ? `Default: ${String(port.default)}`
              : "Enter string..."
          }
          value={strVal}
          onChange={(e) =>
            onChange(e.target.value === "" ? undefined : e.target.value)
          }
          className="w-full rounded border border-slate-700 bg-slate-950 p-2 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
        />
      ) : (
        <input
          data-testid={testId}
          type="text"
          disabled={readOnly}
          placeholder={
            port.default !== null && port.default !== undefined
              ? `Default: ${String(port.default)}`
              : "Enter string..."
          }
          value={strVal}
          onChange={(e) =>
            onChange(e.target.value === "" ? undefined : e.target.value)
          }
          className="w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
        />
      )}
      {!readOnly && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setMultiline((m) => !m)}
            className="text-[10px] text-slate-500 hover:text-slate-300"
          >
            {multiline ? "Single line" : "Multiline / code"}
          </button>
        </div>
      )}
    </div>
  );
}
