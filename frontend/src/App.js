import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline, LinearProgress, ThemeProvider, createTheme } from '@mui/material';
import AppShell from './components/AppShell';
import './App.css';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'));

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#22c55e', light: '#4ade80', dark: '#16a34a' },
    secondary: { main: '#0ea5e9', light: '#38bdf8', dark: '#0284c7' },
    background: {
      default: '#0f1117',
      paper: '#1a1d27',
    },
    text: {
      primary: '#e2e8f0',
      secondary: '#94a3b8',
    },
    divider: 'rgba(148,163,184,0.12)',
    success: { main: '#22c55e' },
    warning: { main: '#f59e0b' },
    error: { main: '#ef4444' },
    info: { main: '#0ea5e9' },
  },
  typography: {
    fontFamily: "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif",
    h3: { fontWeight: 700, letterSpacing: '-0.02em' },
    h4: { fontWeight: 700, letterSpacing: '-0.01em' },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    subtitle2: { fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.08em' },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiCard: {
      defaultProps: { variant: 'outlined' },
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          borderColor: 'rgba(148,163,184,0.12)',
          transition: 'border-color 0.2s, box-shadow 0.2s',
          '&:hover': {
            borderColor: 'rgba(34,197,94,0.4)',
            boxShadow: '0 0 20px rgba(34,197,94,0.06)',
          },
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600 },
        contained: {
          background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
          '&:hover': { background: 'linear-gradient(135deg, #4ade80 0%, #22c55e 100%)' },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500 },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 500, minHeight: 48 },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { borderRadius: 4 },
        bar: { background: 'linear-gradient(90deg, #22c55e, #0ea5e9)' },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'small' },
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AppShell>
          <Suspense fallback={<LinearProgress sx={{ mx: 3, mt: 10 }} />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/projects/:projectId" element={<ProjectDetail />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AppShell>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
