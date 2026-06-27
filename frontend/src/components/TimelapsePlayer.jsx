import { useCallback, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  TextField,
  Typography,
} from '@mui/material';
import SatelliteAltIcon from '@mui/icons-material/SatelliteAlt';
import { timelapseAPI } from '../api/client';

function TimelapsePlayer({ projectId }) {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [videoUrl, setVideoUrl] = useState('');
  const [error, setError] = useState('');

  const isGeeError = (msg) =>
    /earth engine|gee|not initialized|credentials/i.test(msg || '');

  const loadTimelapse = useCallback(async () => {
    if (!startDate || !endDate) return;
    setLoading(true);
    setError('');
    setVideoUrl('');
    try {
      const res = await timelapseAPI.getUrl(projectId, startDate, endDate);
      const url = res.data?.url || '';
      if (url) {
        setVideoUrl(url);
      } else {
        setError(res.data?.detail || 'Timelapse generated but no video URL was returned.');
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const status = err?.response?.status;
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
            : 'Failed to load timelapse.';

      // Show a friendly message for GEE / dependency issues
      if (status === 501 || status === 502 || isGeeError(msg)) {
        setError('__GEE_NOT_CONFIGURED__');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [projectId, startDate, endDate]);

  return (
    <Card variant="outlined">
      <CardHeader
        title="Satellite Timelapse"
        avatar={<SatelliteAltIcon sx={{ color: 'primary.main' }} />}
      />
      <CardContent>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-end', mb: 2 }}>
          <TextField
            type="date"
            label="Start Date"
            size="small"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            type="date"
            label="End Date"
            size="small"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
          <Button
            variant="contained"
            size="small"
            onClick={loadTimelapse}
            disabled={!startDate || !endDate || loading}
            startIcon={loading ? <CircularProgress size={16} /> : <SatelliteAltIcon />}
          >
            {loading ? 'Generating…' : 'Generate Timelapse'}
          </Button>
        </Box>

        {/* GEE not configured — friendly message */}
        {error === '__GEE_NOT_CONFIGURED__' && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Google Earth Engine Not Configured
            </Typography>
            <Typography variant="body2">
              Timelapse generation requires Google Earth Engine (GEE) authentication.
              To enable this feature:
            </Typography>
            <Box component="ol" sx={{ mt: 1, pl: 2, '& li': { mb: 0.5 } }}>
              <li>
                <Typography variant="body2">
                  Run <code>earthengine authenticate</code> in your terminal
                </Typography>
              </li>
              <li>
                <Typography variant="body2">
                  Set the <code>GEE_PROJECT</code> environment variable to your GEE cloud project ID
                </Typography>
              </li>
              <li>
                <Typography variant="body2">
                  Restart the backend server
                </Typography>
              </li>
            </Box>
          </Alert>
        )}

        {/* Regular errors */}
        {error && error !== '__GEE_NOT_CONFIGURED__' && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {videoUrl && (
          <Box sx={{ borderRadius: 1, overflow: 'hidden' }}>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video
              src={videoUrl}
              controls
              style={{ width: '100%', maxHeight: 480, background: '#000' }}
            />
          </Box>
        )}

        {!videoUrl && !error && !loading && (
          <Alert severity="info" variant="outlined">
            Select a date range and click <strong>Generate Timelapse</strong> to create a
            Sentinel-2 satellite imagery animation for this project boundary.
            <br />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Requires Google Earth Engine authentication on the server.
            </Typography>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

export default TimelapsePlayer;
