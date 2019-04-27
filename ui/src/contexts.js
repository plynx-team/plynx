import React from "react";

const ResourceContext = React.createContext({});

export const ResourceProvider = ResourceContext.Provider;
export const ResourceConsumer = ResourceContext.Consumer;
