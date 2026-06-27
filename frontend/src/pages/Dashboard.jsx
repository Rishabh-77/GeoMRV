import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Container,
  Grid,
  LinearProgress,
  Snackbar,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import ForestIcon from '@mui/icons-material/Forest';
import GrassIcon from '@mui/icons-material/Grass';
import AgricultureIcon from '@mui/icons-material/Agriculture';
import NatureIcon from '@mui/icons-material/Nature';
import ProjectForm from '../components/ProjectForm';
import { projectAPI } from '../api/client';

const TYPE_CONFIG = {
  forest:        { icon: <ForestIcon />,      gradient: 'linear-gradient(135deg,#22c55e,#15803d)' },
  agroforestry:  { icon: <NatureIcon />,      gradient: 'linear-gradient(135deg,#84cc16,#4d7c0f)' },
  crop:          { icon: <AgricultureIcon />, gradient: 'linear-gradient(135deg,#f59e0b,#b45309)' },
  regenerative:  { icon: <GrassIcon />,       gradient: 'linear-gradient(135deg,#06b6d4,#0e7490)' },
};

function Dashboard() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [toastMessage, setToastMessage] = useState('');

  useEffect(() => { loadProjects(); }, []);

  const loadProjects = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await projectAPI.list();
      setProjects(Array.isArray(response.data) ? response.data : []);
    } catch (apiError) {
      setError(apiError?.response?.data?.detail || 'Failed to load projects.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async (formData) => {
    setSubmitting(true);
    setError('');
    try {
      // Extract boundary geojson before sending to API
      const { _boundary_geojson, ...projectData } = formData;

      const response = await projectAPI.create(projectData);
      const newProjectId = response.data?.id;

      // If user drew a boundary, upload it as a GeoJSON file
      if (_boundary_geojson && newProjectId) {
        try {
          const blob = new Blob([JSON.stringify(_boundary_geojson)], { type: 'application/json' });
          const file = new File([blob], 'boundary.geojson', { type: 'application/json' });
          await projectAPI.uploadBoundary(newProjectId, file);
          setToastMessage('Project created with boundary!');
        } catch {
          setToastMessage('Project created, but boundary upload failed. You can re-upload later.');
        }
      } else {
        setToastMessage('Project created successfully.');
      }

      setShowForm(false);
      await loadProjects();
    } catch (apiError) {
      setError(apiError?.response?.data?.detail || 'Failed to create project.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* ── Hero ── */}
      <Box
        sx={{
          background: 'linear-gradient(180deg, rgba(34,197,94,0.08) 0%, transparent 100%)',
          borderBottom: '1px solid',
          borderColor: 'divider',
          py: { xs: 4, md: 6 },
          px: 3,
        }}
      >
        <Container maxWidth="lg">
          <Typography variant="h3" component="h1" gutterBottom>
            Projects
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 520 }}>
            Monitor, verify, and generate audit-ready evidence for nature-based carbon projects across India.
          </Typography>

          {/* Quick stats */}
          <Grid container spacing={2} sx={{ mt: 3 }}>
            {[
              { label: 'Total Projects', value: projects.length, color: '#22c55e' },
              { label: 'Forest', value: projects.filter(p => p.project_type === 'forest').length, color: '#4ade80' },
              { label: 'Agroforestry', value: projects.filter(p => p.project_type === 'agroforestry').length, color: '#84cc16' },
              { label: 'Total Area', value: `${projects.reduce((s, p) => s + (p.total_area_ha || 0), 0).toLocaleString()} ha`, color: '#0ea5e9' },
            ].map((stat) => (
              <Grid item xs={6} md={3} key={stat.label}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <Typography variant="subtitle2" color="text.secondary">
                    {stat.label}
                  </Typography>
                  <Typography variant="h5" sx={{ color: stat.color, fontWeight: 700 }}>
                    {stat.value}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* ── Content ── */}
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5">All Projects</Typography>
          <Button
            variant="contained"
            startIcon={showForm ? null : <AddIcon />}
            onClick={() => setShowForm((p) => !p)}
          >
            {showForm ? 'Cancel' : 'New Project'}
          </Button>
        </Box>

        {showForm && (
          <ProjectForm
            onSubmit={handleCreateProject}
            onCancel={() => setShowForm(false)}
            submitting={submitting}
          />
        )}

        {loading && <LinearProgress sx={{ mb: 3 }} />}

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {!loading && projects.length === 0 && (
          <Box
            sx={{
              py: 8,
              textAlign: 'center',
              border: '1px dashed',
              borderColor: 'divider',
              borderRadius: 3,
            }}
          >
            <FolderOpenIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography color="text.secondary">
              No projects yet. Click <strong>New Project</strong> to get started.
            </Typography>
          </Box>
        )}

        <Grid container spacing={2.5}>
          {projects.map((project) => {
            const cfg = TYPE_CONFIG[project.project_type] || TYPE_CONFIG.forest;
            return (
              <Grid item key={project.id} xs={12} sm={6} lg={4}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                    overflow: 'visible',
                  }}
                >
                  {/* Accent bar */}
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      height: 3,
                      borderRadius: '12px 12px 0 0',
                      background: cfg.gradient,
                    }}
                  />

                  <CardActionArea
                    onClick={() => navigate(`/projects/${project.id}`)}
                    sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', alignItems: 'stretch', justifyContent: 'flex-start' }}
                  >
                    <CardContent sx={{ flexGrow: 1, pt: 3 }}>
                      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, mb: 2 }}>
                        <Avatar
                          sx={{
                            width: 40,
                            height: 40,
                            background: cfg.gradient,
                            fontSize: 20,
                          }}
                        >
                          {cfg.icon}
                        </Avatar>
                        <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                          <Typography variant="h6" noWrap sx={{ fontSize: '1rem' }}>
                            {project.name}
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              mt: 0.25,
                            }}
                          >
                            {project.description || 'No description'}
                          </Typography>
                        </Box>
                      </Box>

                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                        {project.project_type && (
                          <Chip
                            label={project.project_type}
                            size="small"
                            sx={{
                              background: 'rgba(34,197,94,0.1)',
                              color: 'primary.light',
                              borderColor: 'rgba(34,197,94,0.3)',
                              border: '1px solid',
                              fontWeight: 600,
                              fontSize: '0.7rem',
                            }}
                          />
                        )}
                        {project.total_area_ha != null && (
                          <Chip
                            label={`${project.total_area_ha} ha`}
                            size="small"
                            variant="outlined"
                            sx={{ borderColor: 'divider', fontSize: '0.7rem' }}
                          />
                        )}
                        {project.region && (
                          <Chip
                            label={project.region}
                            size="small"
                            variant="outlined"
                            sx={{ borderColor: 'divider', fontSize: '0.7rem' }}
                          />
                        )}
                      </Box>
                    </CardContent>
                  </CardActionArea>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      </Container>

      <Snackbar
        open={Boolean(toastMessage)}
        autoHideDuration={2500}
        onClose={() => setToastMessage('')}
      >
        <Alert onClose={() => setToastMessage('')} severity="success" variant="filled">
          {toastMessage}
        </Alert>
      </Snackbar>
    </>
  );
}

export default Dashboard;
