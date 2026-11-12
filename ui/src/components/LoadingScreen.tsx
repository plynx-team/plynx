import React, { CSSProperties } from 'react';
import './LoadingScreen.css';

export interface LoadingScreenProps {
  style?: CSSProperties;
  className?: string;
  text?: string;
}

export const LoadingScreen: React.FC<LoadingScreenProps> = ({
  style,
  className = '',
  text = 'Loading...',
}) => (
  <div className={`LoadingScreen ${className}`.trim()} style={style}>
    <div className="loader">{text}</div>
  </div>
);

export const SimpleLoader: React.FC<LoadingScreenProps> = ({
  style,
  className = '',
  text = 'Loading...',
}) => (
  <div className={`simple-loader ${className}`.trim()} style={style}>
    <div className="loader">{text}</div>
  </div>
);

export default LoadingScreen;
