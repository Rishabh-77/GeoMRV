import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Box,
  Button,
  Chip,
  Toolbar,
  Typography,
} from '@mui/material';
import SatelliteAltIcon from '@mui/icons-material/SatelliteAlt';
import DashboardIcon from '@mui/icons-material/Dashboard';

function AppShell({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const isHome = location.pathname === '/';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* ── Top Bar ── */}
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          background: 'rgba(15,17,23,0.85)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(148,163,184,0.1)',
        }}
      >
        <Toolbar sx={{ gap: 1.5 }}>
          {/* Logo / Brand */}
          <Box
            onClick={() => navigate('/')}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              cursor: 'pointer',
              mr: 2,
              '&:hover .logo-icon': { color: 'primary.light' },
            }}
          >
            <SatelliteAltIcon
              className="logo-icon"
              sx={{
                fontSize: 28,
                color: 'primary.main',
                transition: 'color 0.2s',
              }}
            />
            <Typography
              variant="h6"
              sx={{
                fontWeight: 800,
                letterSpacing: '-0.03em',
                background: 'linear-gradient(135deg, #22c55e 30%, #0ea5e9 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              GeoMRV
            </Typography>
          </Box>

          <Chip
            label="BETA"
            size="small"
            sx={{
              height: 20,
              fontSize: '0.6rem',
              fontWeight: 700,
              letterSpacing: '0.05em',
              background: 'rgba(34,197,94,0.15)',
              color: 'primary.main',
              border: '1px solid rgba(34,197,94,0.3)',
            }}
          />

          <Box sx={{ flexGrow: 1 }} />

          {/* Nav links */}
          {!isHome && (
            <Button
              startIcon={<DashboardIcon />}
              onClick={() => navigate('/')}
              sx={{ color: 'text.secondary', '&:hover': { color: 'text.primary' } }}
            >
              Dashboard
            </Button>
          )}

          <Chip
            label="India"
            size="small"
            variant="outlined"
            sx={{ borderColor: 'divider', color: 'text.secondary' }}
          />
        </Toolbar>
      </AppBar>

      {/* ── Page Content ── */}
      <Box component="main" sx={{ flexGrow: 1 }}>
        {children}
      </Box>

      {/* ── Footer ── */}
      <Box
        component="footer"
        sx={{
          py: 2,
          px: 3,
          textAlign: 'center',
          borderTop: '1px solid',
          borderColor: 'divider',
          color: 'text.secondary',
          fontSize: '0.75rem',
        }}
      >
        GeoMRV &middot; Digital Biomass Verification for Indian Carbon Credits
      </Box>
    </Box>
  );
}

export default AppShell;
