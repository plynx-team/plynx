import React, { useMemo } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

export function withRouter(Component) {
  function ComponentWithRouterProp(props) {
    const location = useLocation();
    const navigate = useNavigate();
    const params = useParams();

    const history = useMemo(
      () => ({
        push: (to) => navigate(to),
        replace: (to) => navigate(to, { replace: true }),
      }),
      [navigate]
    );

    const match = useMemo(() => ({ params }), [params]);

    return (
      <Component
        {...props}
        location={location}
        history={history}
        match={match}
      />
    );
  }

  ComponentWithRouterProp.displayName = `withRouter(${Component.displayName || Component.name || 'Component'})`;
  return ComponentWithRouterProp;
}
