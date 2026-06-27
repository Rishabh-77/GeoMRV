import { useCallback, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Grid,
  MenuItem,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import MapIcon from '@mui/icons-material/Map';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DrawableMap from './DrawableMap';

const PROJECT_TYPES = [
  { value: 'forest', label: 'Forest' },
  { value: 'agroforestry', label: 'Agroforestry' },
  { value: 'crop', label: 'Crop' },
  { value: 'regenerative', label: 'Regenerative' },
];

const STEPS = ['Project Details', 'Draw Boundary'];

const initialFormState = {
  name: '',
  description: '',
  location_name: '',
  country: 'India',
  region: '',
  total_area_ha: '',
  project_type: 'forest',
  start_date: '',
};

function ProjectForm({ onSubmit, onCancel, submitting = false }) {
  const [formData, setFormData] = useState(initialFormState);
  const [activeStep, setActiveStep] = useState(0);
  const [drawnGeoJson, setDrawnGeoJson] = useState(null);
  const [drawnAreaHa, setDrawnAreaHa] = useState(0);
  const fileInputRef = useRef(null);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  /* Map draw callback */
  const handleGeoJsonChange = useCallback((geojson, areaHa) => {
    setDrawnGeoJson(geojson);
    setDrawnAreaHa(areaHa);
  }, []);

  /* GeoJSON file import */
  const handleFileImport = useCallback((event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target.result);
        setDrawnGeoJson(parsed);
      } catch {
        /* ignore parse errors */
      }
    };
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  /* Step validation */
  const isStep1Valid = formData.name.trim().length > 0;

  /* Submit */
  const handleSubmit = () => {
    const areaToUse = drawnAreaHa || (formData.total_area_ha ? Number(formData.total_area_ha) : null);

    const payload = {
      ...formData,
      total_area_ha: areaToUse,
      start_date: formData.start_date || null,
      description: formData.description || null,
      location_name: formData.location_name || null,
      country: formData.country || null,
      region: formData.region || null,
      project_type: formData.project_type || null,
      _boundary_geojson: drawnGeoJson,
    };

    onSubmit(payload);
  };

  return (
    <Collapse in>
      <Card
        sx={{
          mb: 3,
          border: '1px solid',
          borderColor: 'rgba(34,197,94,0.25)',
          background: 'rgba(34,197,94,0.03)',
        }}
      >
        <CardContent sx={{ p: { xs: 2, md: 3 } }}>
          {/* Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
            <AddCircleOutlineIcon sx={{ color: 'primary.main' }} />
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              New Project
            </Typography>
          </Box>

          {/* Stepper */}
          <Stepper
            activeStep={activeStep}
            alternativeLabel
            sx={{
              mb: 4,
              '& .MuiStepIcon-root.Mui-active': { color: 'primary.main' },
              '& .MuiStepIcon-root.Mui-completed': { color: 'primary.main' },
            }}
          >
            {STEPS.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>

          {/* ── Step 1: Project Details ── */}
          {activeStep === 0 && (
            <Box>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <TextField
                    name="name"
                    label="Project Name *"
                    value={formData.name}
                    onChange={handleChange}
                    fullWidth
                    placeholder="e.g. Sundarbans Reserve"
                    autoFocus
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    name="project_type"
                    select
                    label="Project Type"
                    value={formData.project_type}
                    onChange={handleChange}
                    fullWidth
                  >
                    {PROJECT_TYPES.map((pt) => (
                      <MenuItem key={pt.value} value={pt.value}>
                        {pt.label}
                      </MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    name="description"
                    label="Description"
                    value={formData.description}
                    onChange={handleChange}
                    fullWidth
                    multiline
                    minRows={2}
                    placeholder="Brief description of the project area and goals"
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    name="location_name"
                    label="Location"
                    value={formData.location_name}
                    onChange={handleChange}
                    fullWidth
                    placeholder="e.g. South 24 Parganas"
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    name="region"
                    label="Region / State"
                    value={formData.region}
                    onChange={handleChange}
                    fullWidth
                    placeholder="e.g. West Bengal"
                  />
                </Grid>
                <Grid item xs={12} md={4}>
                  <TextField
                    name="country"
                    label="Country"
                    value={formData.country}
                    onChange={handleChange}
                    fullWidth
                  />
                </Grid>
                <Grid item xs={12} md={4}>
                  <TextField
                    name="total_area_ha"
                    label="Total Area (ha)"
                    type="number"
                    value={formData.total_area_ha}
                    onChange={handleChange}
                    fullWidth
                    inputProps={{ min: 0, step: 'any' }}
                    helperText="Auto-calculated if you draw on map"
                  />
                </Grid>
                <Grid item xs={12} md={4}>
                  <TextField
                    name="start_date"
                    label="Start Date"
                    type="date"
                    value={formData.start_date}
                    onChange={handleChange}
                    fullWidth
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
              </Grid>

              <Box sx={{ mt: 3, display: 'flex', gap: 1.5, justifyContent: 'flex-end' }}>
                <Button
                  variant="outlined"
                  onClick={onCancel}
                  sx={{ borderColor: 'divider', color: 'text.secondary' }}
                >
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  endIcon={<ArrowForwardIcon />}
                  disabled={!isStep1Valid}
                  onClick={() => setActiveStep(1)}
                >
                  Next: Draw Area
                </Button>
              </Box>
            </Box>
          )}

          {/* ── Step 2: Draw Boundary ── */}
          {activeStep === 1 && (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <MapIcon sx={{ color: 'primary.main' }} />
                  <Typography variant="body1" sx={{ fontWeight: 600 }}>
                    Draw your project boundary on the map
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  {drawnAreaHa > 0 && (
                    <Chip
                      label={`${drawnAreaHa.toLocaleString()} ha`}
                      color="primary"
                      size="small"
                      sx={{ fontWeight: 700 }}
                    />
                  )}
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<CloudUploadIcon />}
                    component="label"
                    sx={{ borderColor: 'divider', color: 'text.secondary' }}
                  >
                    Import GeoJSON
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".geojson,.json"
                      hidden
                      onChange={handleFileImport}
                    />
                  </Button>
                </Box>
              </Box>

              <Alert
                severity="info"
                variant="outlined"
                sx={{ mb: 2, borderColor: 'rgba(14,165,233,0.3)' }}
              >
                Use the <strong>polygon</strong> or <strong>rectangle</strong> tool (top-right) to draw your project area.
                You can also import an existing GeoJSON file. The area is optional — you can skip and add it later.
              </Alert>

              {/* The map */}
              <Box sx={{ borderRadius: 3, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
                <DrawableMap
                  existingGeoJson={drawnGeoJson}
                  onGeoJsonChange={handleGeoJsonChange}
                  height={500}
                />
              </Box>

              {/* Actions */}
              <Box sx={{ mt: 3, display: 'flex', gap: 1.5, justifyContent: 'space-between' }}>
                <Button
                  variant="outlined"
                  startIcon={<ArrowBackIcon />}
                  onClick={() => setActiveStep(0)}
                  sx={{ borderColor: 'divider', color: 'text.secondary' }}
                >
                  Back
                </Button>

                <Box sx={{ display: 'flex', gap: 1.5 }}>
                  <Button
                    variant="outlined"
                    onClick={onCancel}
                    disabled={submitting}
                    sx={{ borderColor: 'divider', color: 'text.secondary' }}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="contained"
                    onClick={handleSubmit}
                    disabled={submitting || !isStep1Valid}
                  >
                    {submitting ? 'Creating…' : drawnGeoJson ? 'Create Project with Boundary' : 'Create Project (no boundary)'}
                  </Button>
                </Box>
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>
    </Collapse>
  );
}

export default ProjectForm;
