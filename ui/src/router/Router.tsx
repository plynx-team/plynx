import React, { createContext, useContext, useEffect, useState } from "react";

export interface RouteMatch {
  path: string;
  params: Record<string, string>;
}

export interface RouterContextValue {
  currentPath: string;
  search: string;
  queryParams: Record<string, string>;
  params: Record<string, string>;
  navigate: (path: string, options?: { replace?: boolean }) => void;
}

const RouterContext = createContext<RouterContextValue>({
  currentPath: "/workflows",
  search: "",
  queryParams: {},
  params: {},
  navigate: () => {},
});

export function useRouter(): RouterContextValue {
  return useContext(RouterContext);
}

export function parseQueryString(search: string): Record<string, string> {
  const params: Record<string, string> = {};
  if (!search) return params;
  const clean = search.startsWith("?") ? search.slice(1) : search;
  for (const part of clean.split("&")) {
    if (!part) continue;
    const [key, value] = part.split("=");
    if (key) {
      params[decodeURIComponent(key)] = value !== undefined ? decodeURIComponent(value) : "";
    }
  }
  return params;
}

export interface ParsedRoute {
  pathname: string;
  search: string;
  queryParams: Record<string, string>;
}

export function parseHash(hash: string): ParsedRoute {
  const clean = hash.replace(/^#\/?/, "");
  if (!clean) {
    return { pathname: "/workflows", search: "", queryParams: {} };
  }
  const qIndex = clean.indexOf("?");
  if (qIndex === -1) {
    return { pathname: `/${clean}`, search: "", queryParams: {} };
  }
  const rawPath = clean.slice(0, qIndex);
  const rawSearch = clean.slice(qIndex);
  return {
    pathname: `/${rawPath}`,
    search: rawSearch,
    queryParams: parseQueryString(rawSearch),
  };
}

export function matchRoute(
  pattern: string,
  actualPath: string,
): { matched: boolean; params: Record<string, string> } {
  const patternParts = pattern.split("/").filter(Boolean);
  const actualParts = actualPath.split("/").filter(Boolean);

  const lastPatternPart =
    patternParts.length > 0 ? patternParts[patternParts.length - 1] : "";
  const isWildcard = lastPatternPart.endsWith("*");

  if (isWildcard) {
    const prefixParts = patternParts.slice(0, -1);
    if (actualParts.length < prefixParts.length) {
      return { matched: false, params: {} };
    }
    const params: Record<string, string> = {};
    for (let i = 0; i < prefixParts.length; i++) {
      const p = prefixParts[i];
      const a = actualParts[i];
      if (p.startsWith(":")) {
        params[p.slice(1)] = decodeURIComponent(a);
      } else if (p !== a) {
        return { matched: false, params: {} };
      }
    }
    const wildcardParamName = lastPatternPart.startsWith(":")
      ? lastPatternPart.slice(1, -1)
      : "path";
    const rest = actualParts
      .slice(prefixParts.length)
      .map((seg) => decodeURIComponent(seg))
      .join("/");
    params[wildcardParamName] = rest;
    return { matched: true, params };
  }

  if (patternParts.length !== actualParts.length) {
    return { matched: false, params: {} };
  }

  const params: Record<string, string> = {};
  for (let i = 0; i < patternParts.length; i++) {
    const p = patternParts[i];
    const a = actualParts[i];
    if (p.startsWith(":")) {
      const paramName = p.slice(1);
      params[paramName] = decodeURIComponent(a);
    } else if (p !== a) {
      return { matched: false, params: {} };
    }
  }

  return { matched: true, params };
}

export function RouterProvider({ children }: { children: React.ReactNode }) {
  const [route, setRoute] = useState<ParsedRoute>(() =>
    typeof window !== "undefined"
      ? parseHash(window.location.hash)
      : { pathname: "/workflows", search: "", queryParams: {} },
  );

  useEffect(() => {
    const handleHashChange = () => {
      setRoute(parseHash(window.location.hash));
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => {
      window.removeEventListener("hashchange", handleHashChange);
    };
  }, []);

  const navigate = (path: string, options?: { replace?: boolean }) => {
    const target = path.startsWith("/") ? path : `/${path}`;
    if (options?.replace && typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.hash = `#${target}`;
      window.history.replaceState(null, "", url);
      setRoute(parseHash(url.hash));
    } else {
      window.location.hash = `#${target}`;
    }
  };

  return (
    <RouterContext.Provider
      value={{
        currentPath: route.pathname,
        search: route.search,
        queryParams: route.queryParams,
        params: {},
        navigate,
      }}
    >
      {children}
    </RouterContext.Provider>
  );
}

export interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string;
  className?: string;
  activeClassName?: string;
}

export function Link({
  to,
  className = "",
  activeClassName = "",
  children,
  onClick,
  ...rest
}: LinkProps) {
  const { currentPath, navigate } = useRouter();
  const target = to.startsWith("/") ? to : `/${to}`;
  const targetPathname = target.split("?")[0];
  const isActive =
    currentPath === targetPathname ||
    (targetPathname !== "/runs" && currentPath.startsWith(targetPathname));

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    // Let browser handle modifier clicks (Cmd+Click, Ctrl+Click, Shift+Click, middle click, etc.)
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
      return;
    }
    e.preventDefault();
    navigate(target);
    if (onClick) {
      onClick(e);
    }
  };

  const finalClassName = `${className} ${isActive ? activeClassName : ""}`.trim();

  return (
    <a
      href={`#${target}`}
      onClick={handleClick}
      className={finalClassName}
      {...rest}
    >
      {children}
    </a>
  );
}
