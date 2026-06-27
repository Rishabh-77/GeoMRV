import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  IconButton,
  LinearProgress,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import MapIcon from '@mui/icons-material/Map';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import BarChartIcon from '@mui/icons-material/BarChart';
import OndemandVideoIcon from '@mui/icons-material/OndemandVideo';
import DescriptionIcon from '@mui/icons-material/Description';
import ForestIcon from '@mui/icons-material/Forest';
import GrassIcon from '@mui/icons-material/Grass';
import AgricultureIcon from '@mui/icons-material/Agriculture';
import NatureIcon from '@mui/icons-material/Nature';
import { projectAPI } from '../api/client';
import BoundaryViewer from '../components/BoundaryViewer';
import JobStatus from '../components/JobStatus';
import ResultsPanel from '../components/ResultsPanel';
import TimelapsePlayer from '../components/TimelapsePlayer';
import EvidenceDownload from '../components/EvidenceDownload';

const TYPE_ICON = {
  forest: <ForestIcon />,
  agroforestry: <NatureIcon />,
  crop: <AgricultureIcon />,
  regenerative: <GrassIcon />,
};

const TYPE_GRADIENT = {
  forest: 'linear-gradient(135deg,#22c55e,#15803d)',
  agroforestry: 'linear-gradient(135deg,#84cc16,#4d7c0f)',
  crop: 'linear-gradient(135deg,#f59e0b,#b45309)',
  regenerative: 'linear-gradient(135deg,#06b6d4,#0e7490)',
};

/* ── Tab panel wrapper ── */
function TabPanel({ children, value, index }) {
  if (value !== index) return null;
  return (
    <Box role="tabpanel" sx={{ pt: 3 }}>
      {children}
    </Box>
  );
}

function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState(0);

  const loadProject = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await projectAPI.get(projectId);
      setProject(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load project.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <LinearProgress />
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        <Button variant="outlined" onClick={() => navigate('/')}>Back to Dashboard</Button>
      </Container>
    );
  }

  const gradient = TYPE_GRADIENT[project?.project_type] || TYPE_GRADIENT.forest;
  const icon = TYPE_ICON[project?.project_type] || TYPE_ICON.forest;

  return (
    <>
      {/* ── Hero Header ── */}
      <Box
        sx={{
          background: `linear-gradient(180deg, rgba(34,197,94,0.06) 0%, transparent 100%)`,
          borderBottom: '1px solid',
          borderColor: 'divider',
          py: { xs: 3, md: 4 },
          px: 3,
        }}
      >
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <IconButton
              onClick={() => navigate('/')}
              size="small"
              aria-label="Back to dashboard"
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                '&:hover': { borderColor: 'primary.main', bgcolor: 'rgba(34,197,94,0.08)' },
              }}
            >
              <ArrowBackIcon fontSize="small" />
            </IconButton>

            <Avatar sx={{ width: 44, height: 44, background: gradient }}>
              {icon}
            </Avatar>

            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography variant="h4" component="h1" noWrap>
                {project?.name}
              </Typography>
              {project?.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                  {project.description}
                </Typography>
              )}
            </Box>
          </Box>

          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, ml: 9.5 }}>
            {project?.project_type && (
              <Chip
                label={project.project_type}
                size="small"
                sx={{
                  background: 'rgba(34,197,94,0.1)',
                  color: 'primary.light',
                  border: '1px solid rgba(34,197,94,0.3)',
                  fontWeight: 600,
                  fontSize: '0.7rem',
                }}
              />
            )}
            {project?.region && (
              <Chip label={project.region} size="small" variant="outlined" sx={{ borderColor: 'divider' }} />
            )}
            {project?.country && (
              <Chip label={project.country} size="small" variant="outlined" sx={{ borderColor: 'divider' }} />
            )}
            {project?.total_area_ha != null && (
              <Chip label={`${project.total_area_ha} ha`} size="small" variant="outlined" sx={{ borderColor: 'divider' }} />
            )}
          </Box>
        </Container>
      </Box>

      {/* ── Tabs + Content ── */}
      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 1 }}>
          <Tabs
            value={tab}
            onChange={(_, v) => setTab(v)}
            variant="scrollable"
            scrollButtons="auto"
            aria-label="Project detail tabs"
            sx={{
              '& .MuiTab-root': { gap: 0.75 },
              '& .Mui-selected': { color: 'primary.main' },
            }}
          >
            <Tab icon={<MapIcon />} iconPosition="start" label="Boundary" />
            <Tab icon={<MonitorHeartIcon />} iconPosition="start" label="Monitoring" />
            <Tab icon={<BarChartIcon />} iconPosition="start" label="Results" />
            <Tab icon={<OndemandVideoIcon />} iconPosition="start" label="Timelapse" />
            <Tab icon={<DescriptionIcon />} iconPosition="start" label="Evidence" />
          </Tabs>
        </Box>

        <TabPanel value={tab} index={0}>
          <BoundaryViewer projectId={projectId} onBoundaryLoaded={loadProject} />
        </TabPanel>
        <TabPanel value={tab} index={1}>
          <JobStatus projectId={projectId} />
        </TabPanel>
        <TabPanel value={tab} index={2}>
          <ResultsPanel projectId={projectId} />
        </TabPanel>
        <TabPanel value={tab} index={3}>
          <TimelapsePlayer projectId={projectId} />
        </TabPanel>
        <TabPanel value={tab} index={4}>
          <EvidenceDownload projectId={projectId} />
        </TabPanel>
      </Container>
    </>
  );
}

export default ProjectDetail;
