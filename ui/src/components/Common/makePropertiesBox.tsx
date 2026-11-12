import React, { ReactNode } from 'react';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';

export interface PropertiesBoxProps {
  title: ReactNode;
  children: ReactNode;
  className?: string;
}

export const PropertiesBox: React.FC<PropertiesBoxProps> = ({ title, children, className = '' }) => (
  <Paper
    elevation={1}
    className={`PropertiesBox ${className}`.trim()}
    sx={{
      backgroundColor: '#262626',
      border: '1px solid #383838',
      borderRadius: '4px',
      marginBottom: '10px',
      overflow: 'hidden',
    }}
  >
    <Box
      className="PropertiesBoxHeader"
      sx={{
        backgroundColor: '#202020',
        padding: '6px 12px',
        borderBottom: '1px solid #333',
      }}
    >
      <Typography variant="subtitle2" component="div" sx={{ fontWeight: 600, color: '#fff' }}>
        {title}
      </Typography>
    </Box>
    <Box className="PropertiesBoxContent" sx={{ padding: '8px 12px' }}>
      {children}
    </Box>
  </Paper>
);

export default function makePropertiesBox(title: ReactNode, content: ReactNode) {
  return <PropertiesBox title={title}>{content}</PropertiesBox>;
}
