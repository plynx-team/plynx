import React, { createContext, useContext, useEffect, useState } from "react";

export interface RouteMatch {
  path: string;
  params: Record<string, string>;
}

export interface RouterContextValue {
  currentPath: string;
  params: Record<string, string>;
  navigate: (path: string) => void;
}

const RouterContext = createContext<RouterContextValue>({
  currentPath: "/workflows",
  params: {},
  navigate: () => {},
});

export function useRouter(): RouterContextValue {
  return useContext(RouterContext);
}

function parseHash(hash: string): string {
  const clean = hash.replace(/^#\/?/, "");
  return clean ? `/${clean}` : "/workflows";
}

export function matchRoute(
  pattern: string,
  actualPath: string,
): { matched: boolean; params: Record<string, string> } {
  const patternParts = pattern.split("/").filter(Boolean);
  const actualParts = actualPath.split("/").filter(Boolean);

  if (patternParts.length !== actualParts.length) {
    // Special case for wildcard or catch-all if last part is :path+
    if (patternParts.length > 0 && patternParts[patternParts.length - 1] === ":path*") {
      const prefixParts = patternParts.slice(0, -1);
      if (actualParts.length >= prefixParts.length) {
        let matched = true;
        for (let i = 0; i < prefixParts.length; i++) {
          if (prefixParts[i] !== actualParts[i]) {
            matched = false;
            break;
          }
        }
        if (matched) {
          const rest = actualParts.slice(prefixParts.length).join("/");
          return { matched: true, params: { path: rest } };
        }
      }
    }
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
  const [currentPath, setCurrentPath] = useState<string>(() =>
    typeof window !== "undefined" ? parseHash(window.location.hash) : "/workflows",
  );

  useEffect(() => {
    const handleHashChange = () => {
      setCurrentPath(parseHash(window.location.hash));
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => {
      window.removeEventListener("hashchange", handleHashChange);
    };
  }, []);

  const navigate = (path: string) => {
    const target = path.startsWith("/") ? path : `/${path}`;
    window.location.hash = `#${target}`;
  };

  return (
    <RouterContext.Provider
      value={{
        currentPath,
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
  const isActive =
    currentPath === target ||
    (target !== "/runs" && currentPath.startsWith(target));

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
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
