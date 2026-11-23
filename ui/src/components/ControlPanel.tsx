import type { ButtonHTMLAttributes, ReactNode } from "react";
import { FeatherIcon, type FeatherIconName } from "./FeatherIcon";

export interface ControlButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: FeatherIconName;
  text: string;
  selected?: boolean;
  variant?: "default" | "primary" | "danger";
}

export function ControlButton({
  icon,
  text,
  selected = false,
  variant = "default",
  className = "",
  disabled,
  ...rest
}: ControlButtonProps) {
  const classes = [
    "control-button",
    selected ? "selected" : "",
    variant !== "default" ? variant : "",
    disabled ? "disabled" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      disabled={disabled}
      className={classes}
      {...rest}
    >
      {icon && <FeatherIcon name={icon} size={15} />}
      <span className="control-button-text">{text}</span>
    </button>
  );
}

export function ControlSeparator() {
  return <span className="control-separator" aria-hidden="true" />;
}

export interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  inputTestId?: string;
}

export function SearchBar({
  value,
  onChange,
  placeholder = "Search...",
  className = "",
  inputTestId,
}: SearchBarProps) {
  return (
    <div className={`SearchBar ${className}`.trim()}>
      <FeatherIcon
        name="search"
        size={14}
        style={{ color: "var(--text-tertiary)" }}
      />
      <input
        type="text"
        data-testid={inputTestId}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {value && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => onChange("")}
          className="text-xs px-1"
          style={{ color: "var(--text-secondary)" }}
        >
          <FeatherIcon name="x" size={13} />
        </button>
      )}
    </div>
  );
}

export function ControlPanel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`control-panel ${className}`.trim()}>{children}</div>;
}
