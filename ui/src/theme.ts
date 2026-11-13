import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    primary: {
      main: '#2680eb',
      light: '#3d91f5',
      dark: '#1b6cd4',
      contrastText: '#fff',
    },
    background: {
      default: '#222222',
      paper: '#2a2a2a',
    },
    text: {
      primary: '#ebebeb',
      secondary: '#b0b0b0',
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
          backgroundColor: '#2a2a2a',
          color: '#ebebeb',
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          color: '#ebebeb',
          borderRadius: '4px',
          fieldset: {
            borderColor: '#404040',
          },
          '&:hover fieldset': {
            borderColor: '#525252',
          },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          color: '#b0b0b0',
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
