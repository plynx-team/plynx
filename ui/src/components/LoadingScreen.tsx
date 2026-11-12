import React, { CSSProperties } from 'react';
import Backdrop from '@mui/material/Backdrop';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
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
  <Backdrop
    open
    className={`LoadingScreen ${className}`.trim()}
    sx={{
      zIndex: 25000,
      color: '#fff',
      backgroundColor: 'rgba(0, 0, 0, 0.65)',
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      ...style,
    }}
  >
    <CircularProgress color="primary" size={54} thickness={4} />
    {text && (
      <Typography variant="body1" component="div" sx={{ color: '#eee', fontWeight: 500 }}>
        {text}
      </Typography>
    )}
  </Backdrop>
);

export const SimpleLoader: React.FC<LoadingScreenProps> = ({
  style,
  className = '',
  text = 'Loading...',
}) => (
  <Box
    className={`simple-loader ${className}`.trim()}
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 1.5,
      padding: 3,
      color: '#eee',
      ...style,
    }}
  >
    <CircularProgress color="primary" size={36} thickness={4} />
    {text && (
      <Typography variant="body2" component="div" sx={{ color: '#aaa' }}>
        {text}
      </Typography>
    )}
  </Box>
);

export default LoadingScreen;
