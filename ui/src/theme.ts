import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    primary: {
      main: '#2196F3',
      light: '#42a5f5',
      dark: '#1565c0',
      contrastText: '#fff',
    },
    background: {
      default: '#333',
      paper: '#404040',
    },
    text: {
      primary: '#fff',
      secondary: '#eee',
    },
  },
  typography: {
    fontFamily: "'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    fontSize: 14,
    body1: { fontSize: '14px', fontWeight: 400 },
    body2: { fontSize: '14px', fontWeight: 400 },
    subtitle1: { fontSize: '16px', fontWeight: 600 },
    button: { fontSize: '14px', fontWeight: 400, textTransform: 'none' },
  },
  components: {
    MuiDialog: {
      styleOverrides: {
        paper: {
          fontFamily: "'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          color: '#eee',
          borderRadius: '5pt',
          fieldset: {
            borderColor: '#999',
          },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          color: '#999',
        },
      },
    },
    MuiListItemIcon: {
      styleOverrides: {
        root: {
          minWidth: '20px',
        },
      },
    },
  },
});

export default theme;
