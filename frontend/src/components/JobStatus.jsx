import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  TextField,
  Typography,
} from '@mui/material';
import { jobAPI } from '../api/client';

const STATUS_COLOURS = {
  pending: 'default',
  running: 'info',
  completed: 'success',
  failed: 'error',
};

const POLL_INTERVAL_MS = 3000;

/* Safely extract a displayable error string from API responses */
function extractErrorMessage(err, fallback = 'Something went wrong.') {
  const detail = err?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === 'object' ? d.msg || JSON.stringify(d) : String(d))).join('; ');
  }
  return JSON.stringify(detail);
}

/* Default date range: last 90 days → today */
function defaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 90);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

function JobStatus({ projectId }) {
  const defaults = defaultDates();
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [startDate, setStartDate] = useState(defaults.start);
  const [endDate, setEndDate] = useState(defaults.end);

  /* ── Load all jobs for this project ── */
  const loadJobs = useCallback(async () => {
    try {
      const res = await jobAPI.list(projectId);
      const data = Array.isArray(res.data) ? res.data : [];
      setJobs(data);
      /* auto-select the most recent job */
      if (data.length > 0 && !activeJobId) {
        setActiveJobId(data[0].id);
      }
    } catch {
      setError('Failed to load jobs.');
    } finally {
      setLoading(false);
    }
  }, [projectId, activeJobId]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  /* ── Poll active job status ── */
  useEffect(() => {
    if (!activeJobId) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await jobAPI.get(activeJobId);
        if (!cancelled) setActiveJob(res.data);
      } catch {
        /* ignore transient errors while polling */
      }
    };

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [activeJobId]);

  /* ── Create new job ── */
  const handleCreateJob = async () => {
    if (!startDate || !endDate) {
      setError('Please select both start and end dates.');
      return;
    }
    setCreating(true);
    setError('');
    try {
      const res = await jobAPI.create({
        project_id: projectId,
        start_date: startDate,
        end_date: endDate,
      });
      setActiveJobId(res.data.id);
      await loadJobs();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to create job.'));
    } finally {
      setCreating(false);
    }
  };

  const isRunning =
    activeJob?.status === 'running' || activeJob?.status === 'pending';

  return (
    <Card variant="outlined">
      <CardHeader
        title="Monitoring Jobs"
      />

      <CardContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* ── New Job form ── */}
        <Box
          sx={{
            mb: 3,
            p: 2,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider',
            background: 'rgba(34,197,94,0.03)',
          }}
        >
          <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
            Run Monitoring Job
          </Typography>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={4}>
              <TextField
                type="date"
                label="Start Date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                size="small"
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                type="date"
                label="End Date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                size="small"
                fullWidth
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <Button
                variant="contained"
                fullWidth
                onClick={handleCreateJob}
                disabled={creating || isRunning || !startDate || !endDate}
              >
                {creating ? 'Creating…' : 'Start Job'}
              </Button>
            </Grid>
          </Grid>
        </Box>

        {loading && <LinearProgress sx={{ mb: 2 }} />}

        {/* Active job summary */}
        {activeJob && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom>
              Active Job
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <Chip
                label={activeJob.status}
                color={STATUS_COLOURS[activeJob.status] || 'default'}
                size="small"
              />
              <Typography variant="body2" color="text.secondary">
                {activeJob.id?.slice(0, 8)}…
              </Typography>
            </Box>

            {isRunning && <LinearProgress sx={{ mb: 1 }} />}

            {activeJob.status === 'completed' && (
              <Alert severity="success" variant="outlined">
                Job completed successfully.
              </Alert>
            )}

            {activeJob.status === 'failed' && (
              <Alert severity="error" variant="outlined">
                {activeJob.error_message || 'Job failed.'}
              </Alert>
            )}
          </Box>
        )}

        {/* Job history list */}
        {jobs.length > 0 && (
          <>
            <Typography variant="subtitle2" gutterBottom>
              History ({jobs.length})
            </Typography>
            <List dense disablePadding>
              {jobs.map((j) => (
                <ListItem
                  key={j.id}
                  disableGutters
                  secondaryAction={
                    <Chip
                      label={j.status}
                      size="small"
                      color={STATUS_COLOURS[j.status] || 'default'}
                    />
                  }
                  onClick={() => setActiveJobId(j.id)}
                  sx={{
                    cursor: 'pointer',
                    bgcolor: j.id === activeJobId ? 'action.selected' : 'transparent',
                    borderRadius: 1,
                    px: 1,
                  }}
                >
                  <ListItemText
                    primary={j.id?.slice(0, 8) + '…'}
                    secondary={j.created_at ? new Date(j.created_at).toLocaleString() : ''}
                  />
                </ListItem>
              ))}
            </List>
          </>
        )}

        {!loading && jobs.length === 0 && (
          <Typography color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
            No monitoring jobs yet. Click <strong>New Job</strong> to start data ingestion.
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

export default JobStatus;
