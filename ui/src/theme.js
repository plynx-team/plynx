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
      default: "#333",
      paper: "#404040",
    },
    text: {
      primary: "#fff",
      secondary: "#eee",
    },
  },
  components: {
    MuiDialog: {
      styleOverrides: {
        paper: {
          fontFamily: "Roboto, Helvetica, Arial, sans-serif",
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          color: "#eee",
          borderRadius: "5pt",
          fieldset: {
            borderColor: "#999",
          },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          color: "#999",
        },
      },
    },
    ListItemIcon: {
      styleOverrides: {
        root: {
          minWidth: "20px",
        },
      },
    },
  },
});

export default theme;
