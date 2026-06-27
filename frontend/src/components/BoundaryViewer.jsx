import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Typography,
} from '@mui/material';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import EditIcon from '@mui/icons-material/Edit';
import { projectAPI } from '../api/client';
import DrawableMap from './DrawableMap';

/* Fix default Leaflet marker icons (CRA asset issue) */
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

/* ── Auto‑fit helper ── */
function FitBounds({ geoJson }) {
  const map = useMap();

  useEffect(() => {
    if (!geoJson) return;
    try {
      const layer = L.geoJSON(geoJson);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
      }
    } catch {
      /* ignore invalid geometry */
    }
  }, [geoJson, map]);

  return null;
}

function BoundaryViewer({ projectId, onBoundaryLoaded }) {
  const [geoData, setGeoData] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loadingExisting, setLoadingExisting] = useState(false);
  const [error, setError] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [drawnAreaHa, setDrawnAreaHa] = useState(0);
  const inputRef = useRef(null);

  /* Fetch existing boundary on mount */
  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;

    const fetchBoundary = async () => {
      setLoadingExisting(true);
      try {
        const res = await projectAPI.getBoundary(projectId);
        if (!cancelled && res.data?.geojson) {
          setGeoData(res.data.geojson);
        }
      } catch {
        /* no boundary yet – that's fine */
      } finally {
        if (!cancelled) setLoadingExisting(false);
      }
    };

    fetchBoundary();
    return () => { cancelled = true; };
  }, [projectId]);

  const handleFileUpload = useCallback(
    async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;

      setUploading(true);
      setError('');

      try {
        await projectAPI.uploadBoundary(projectId, file);

        /* Parse the file locally so we can render immediately */
        const text = await file.text();
        const parsed = JSON.parse(text);
        setGeoData(parsed);
        onBoundaryLoaded?.();
      } catch (err) {
        setError(err?.response?.data?.detail || 'Failed to upload boundary.');
      } finally {
        setUploading(false);
        /* reset input so the same file can be re-selected */
        if (inputRef.current) inputRef.current.value = '';
      }
    },
    [projectId, onBoundaryLoaded],
  );

  /* Save drawn boundary */
  const handleDrawnSave = useCallback(
    async (geojson) => {
      if (!geojson) return;
      setUploading(true);
      setError('');
      try {
        const blob = new Blob([JSON.stringify(geojson)], { type: 'application/json' });
        const file = new File([blob], 'boundary.geojson', { type: 'application/json' });
        await projectAPI.uploadBoundary(projectId, file);
        setGeoData(geojson);
        setEditMode(false);
        onBoundaryLoaded?.();
      } catch (err) {
        setError(err?.response?.data?.detail || 'Failed to save drawn boundary.');
      } finally {
        setUploading(false);
      }
    },
    [projectId, onBoundaryLoaded],
  );

  const handleGeoJsonChange = useCallback((geojson, areaHa) => {
    setDrawnAreaHa(areaHa);
    // Store latest drawn geojson for save
    handleDrawnSave._latestGeoJson = geojson;
  }, [handleDrawnSave]);

  return (
    <Card variant="outlined">
      <CardHeader
        title="Project Boundary"
        action={
          <Box sx={{ display: 'flex', gap: 1 }}>
            {!editMode && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<EditIcon />}
                onClick={() => setEditMode(true)}
                sx={{ borderColor: 'divider', color: 'text.secondary' }}
              >
                Draw on Map
              </Button>
            )}
            <Button
              variant="contained"
              size="small"
              component="label"
              disabled={uploading}
              startIcon={uploading ? <CircularProgress size={16} /> : <CloudUploadIcon />}
            >
              {uploading ? 'Uploading…' : 'Upload GeoJSON'}
              <input
                ref={inputRef}
                type="file"
                accept=".geojson,.json"
                hidden
                onChange={handleFileUpload}
              />
            </Button>
          </Box>
        }
      />

      <CardContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {loadingExisting && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        )}

        {/* ── Draw mode ── */}
        {editMode && (
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Draw a polygon or rectangle, then click <strong>Save Boundary</strong>.
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                {drawnAreaHa > 0 && (
                  <Chip label={`${drawnAreaHa.toLocaleString()} ha`} color="primary" size="small" sx={{ fontWeight: 700 }} />
                )}
                <Button
                  variant="contained"
                  size="small"
                  disabled={uploading}
                  onClick={() => {
                    if (handleDrawnSave._latestGeoJson) handleDrawnSave(handleDrawnSave._latestGeoJson);
                  }}
                >
                  Save Boundary
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setEditMode(false)}
                  sx={{ borderColor: 'divider', color: 'text.secondary' }}
                >
                  Cancel
                </Button>
              </Box>
            </Box>
            <Box sx={{ borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
              <DrawableMap
                existingGeoJson={geoData}
                onGeoJsonChange={handleGeoJsonChange}
                height={480}
              />
            </Box>
          </Box>
        )}

        {/* ── View mode ── */}
        {!editMode && !loadingExisting && !geoData && (
          <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
            No boundary uploaded yet. Upload a GeoJSON file or draw directly on the map.
          </Typography>
        )}

        {!editMode && geoData && (
          <Box sx={{ height: 420, borderRadius: 2, overflow: 'hidden' }}>
            <MapContainer
              center={[20.5937, 78.9629]}
              zoom={5}
              style={{ height: '100%', width: '100%' }}
              scrollWheelZoom
            >
              <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                attribution="Tiles &copy; Esri"
                maxZoom={18}
              />
              <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
                maxZoom={18}
              />
              <GeoJSON
                key={JSON.stringify(geoData).slice(0, 80)}
                data={geoData}
                style={{ color: '#22c55e', weight: 2.5, fillOpacity: 0.18, fillColor: '#22c55e' }}
              />
              <FitBounds geoJson={geoData} />
            </MapContainer>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

export default BoundaryViewer;
