import React from "react";

const PluginsContext = React.createContext({});

export const PluginsProvider = PluginsContext.Provider;
export const PluginsConsumer = PluginsContext.Consumer;
