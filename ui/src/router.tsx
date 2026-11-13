import React, { useMemo, ComponentType } from 'react';
import { useLocation, useNavigate, useParams, Location, Params } from 'react-router-dom';

export type RouterLocation = Location;

export interface RouterHistory {
  push: (to: string | { pathname?: string; search?: string; hash?: string }) => void;
  replace: (to: string | { pathname?: string; search?: string; hash?: string }) => void;
}

export interface RouterMatch {
  params: Params<string>;
}

export interface WithRouterProps {
  location: Location;
  history: RouterHistory;
  match: RouterMatch;
}

export function withRouter<P extends object>(
  WrappedComponent: ComponentType<P>
): React.FC<Omit<P, keyof WithRouterProps> & Partial<WithRouterProps>> {
  function ComponentWithRouterProp(props: any) {
    const location = useLocation();
    const navigate = useNavigate();
    const params = useParams();

    const history = useMemo<RouterHistory>(
      () => ({
        push: (to: string | { pathname?: string; search?: string; hash?: string }) => navigate(to as any),
        replace: (to: string | { pathname?: string; search?: string; hash?: string }) => navigate(to as any, { replace: true }),
      }),
      [navigate]
    );

    const match = useMemo<RouterMatch>(() => ({ params }), [params]);

    return (
      <WrappedComponent
        {...(props as P)}
        location={location}
        history={history}
        match={match}
      />
    );
  }

  ComponentWithRouterProp.displayName = `withRouter(${WrappedComponent.displayName || WrappedComponent.name || 'Component'})`;
  return ComponentWithRouterProp;
}

