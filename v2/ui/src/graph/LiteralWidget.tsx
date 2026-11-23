import type { InputPortSpec } from "../api/types.gen";
import { PortInput } from "../components/PortInput";

export interface LiteralWidgetProps {
  port: InputPortSpec;
  value: unknown;
  readOnly?: boolean;
  onChange: (value: unknown) => void;
  testIdPrefix?: string;
}

/** Thin wrapper delegating to the unified PortInput component. */
export function LiteralWidget({
  port,
  value,
  readOnly = false,
  onChange,
  testIdPrefix = "inspector-input",
}: LiteralWidgetProps) {
  return (
    <PortInput
      port={port}
      value={value}
      readOnly={readOnly}
      onChange={(nextVal) => onChange(nextVal)}
      testId={`${testIdPrefix}-${port.name}`}
      showPresets={true}
      allowListEditor={true}
    />
  );
}
