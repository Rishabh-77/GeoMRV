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
  Dialog,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  LinearProgress,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import SatelliteAltIcon from '@mui/icons-material/SatelliteAlt';
import CloseIcon from '@mui/icons-material/Close';
import CloudIcon from '@mui/icons-material/Cloud';
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip as ChartTooltip,
  Legend as ChartLegend,
  Title as ChartTitle,
} from 'chart.js';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import { jobAPI, featureAPI, verificationAPI, mlAPI, thumbnailAPI } from '../api/client';

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  ChartTooltip,
  ChartLegend,
  ChartTitle,
);

/* ── helpers ── */
function fmt(val, decimals = 2) {
  if (val == null) return '—';
  return Number(val).toFixed(decimals);
}
function extractError(err, fallback = 'Something went wrong.') {
  const detail = err?.response?.data?.detail;
  if (!detail) return err?.message || fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail))
    return detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
  if (typeof detail === 'object') return detail.message || JSON.stringify(detail);
  return String(detail);
}

const STATUS_CHIP = { PASS: 'success', REVIEW_REQUIRED: 'warning', FAIL: 'error' };
const PIPELINE_STEPS = ['Feature Extraction', 'Verification', 'ML Scoring'];

/** Human-friendly NDVI interpretation */
function ndviHealth(ndvi) {
  if (ndvi == null) return { label: 'No data', emoji: '❓', color: '#888', desc: 'No vegetation reading available.' };
  if (ndvi < 0.1) return { label: 'Bare / Water', emoji: '🏜️', color: '#ef4444', desc: 'Little to no vegetation detected. This area appears to be bare soil, rock, or water.' };
  if (ndvi < 0.2) return { label: 'Very Sparse', emoji: '🌵', color: '#f97316', desc: 'Minimal vegetation. Could be arid land, recently cleared area, or early-stage planting.' };
  if (ndvi < 0.35) return { label: 'Sparse Vegetation', emoji: '🌱', color: '#f59e0b', desc: 'Light vegetation cover. Typical of grasslands, young crops, or degraded forest areas.' };
  if (ndvi < 0.5) return { label: 'Moderate Vegetation', emoji: '🌿', color: '#84cc16', desc: 'Healthy moderate vegetation. Typical of shrublands, maturing crops, or open woodland.' };
  if (ndvi < 0.7) return { label: 'Healthy Vegetation', emoji: '🌳', color: '#22c55e', desc: 'Good vegetation density. Consistent with healthy forests, active cropland, or well-maintained plantations.' };
  return { label: 'Dense / Lush Vegetation', emoji: '🌲', color: '#16a34a', desc: 'Very dense, healthy vegetation. Indicates mature forest, peak crop growth, or thriving plantation.' };
}

/** Clean up data source names for humans */
function friendlySource(src) {
  if (!src) return 'Sentinel-2';
  return src
    .replace(/_SR_Harmonized/gi, '')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/* ================================================================
   ResultsPanel – Observations + Full Analysis Pipeline
   ================================================================ */
function ResultsPanel({ projectId }) {
  // Observations (always available after a monitoring job)
  const [observations, setObservations] = useState([]);
  const [obsLoading, setObsLoading] = useState(true);

  // Selected observation (clicked data point or card)
  const [selectedObs, setSelectedObs] = useState(null);

  // Pipeline results
  const [features, setFeatures] = useState(null);
  const [verification, setVerification] = useState(null);
  const [mlResult, setMlResult] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(true);

  // Pipeline execution
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(-1);
  const [pipelineError, setPipelineError] = useState('');
  const [pipelineDone, setPipelineDone] = useState(false);

  // Date range for analysis
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [error, setError] = useState('');

  // Ref for chart interaction
  const chartRef = useRef(null);

  // Thumbnail state
  const [thumbData, setThumbData] = useState(null);   // { url, ndvi_url, ... }
  const [thumbLoading, setThumbLoading] = useState(false);
  const [thumbError, setThumbError] = useState('');
  const [showNdviImage, setShowNdviImage] = useState(false); // toggle RGB vs NDVI

  /* ── Fetch satellite thumbnail when a data point is selected ── */
  useEffect(() => {
    if (!selectedObs || !projectId) {
      setThumbData(null);
      setThumbError('');
      return;
    }
    let cancelled = false;
    setThumbLoading(true);
    setThumbError('');
    setThumbData(null);
    setShowNdviImage(false);

    thumbnailAPI
      .get(projectId, selectedObs.observation_date)
      .then((res) => {
        if (!cancelled) {
          if (res.data?.url) {
            setThumbData(res.data);
          } else {
            setThumbError(res.data?.detail || 'No image available for this date.');
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const status = err?.response?.status;
          if (status === 501 || status === 502) {
            setThumbError('Satellite imagery service is not configured.');
          } else {
            setThumbError('Could not load satellite image.');
          }
        }
      })
      .finally(() => {
        if (!cancelled) setThumbLoading(false);
      });

    return () => { cancelled = true; };
  }, [selectedObs, projectId]);

  /* ── Load existing observations ── */
  const loadObservations = useCallback(async () => {
    setObsLoading(true);
    try {
      const res = await jobAPI.observations(projectId);
      const data = Array.isArray(res.data) ? res.data : [];
      setObservations(data);

      // Auto-detect date range from observations
      if (data.length > 0) {
        const dates = data
          .map((o) => o.observation_date)
          .filter(Boolean)
          .sort();
        if (dates.length > 0 && !startDate) {
          setStartDate(dates[0]);
          setEndDate(dates[dates.length - 1]);
        }
      }
    } catch {
      setObservations([]);
    } finally {
      setObsLoading(false);
    }
  }, [projectId, startDate]);

  /* ── Load existing analysis results ── */
  const loadResults = useCallback(async () => {
    setResultsLoading(true);
    try {
      const [featRes, verRes, mlRes] = await Promise.allSettled([
        featureAPI.latest(projectId),
        verificationAPI.latest(projectId),
        mlAPI.latest(projectId),
      ]);
      if (featRes.status === 'fulfilled')
        setFeatures(featRes.value.data?.features ?? null);
      if (verRes.status === 'fulfilled')
        setVerification(
          verRes.value.data?.verification ?? verRes.value.data ?? null,
        );
      if (mlRes.status === 'fulfilled') setMlResult(mlRes.value.data ?? null);
    } catch {
      // silently ignore – we'll show the "run pipeline" prompt
    } finally {
      setResultsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadObservations();
    loadResults();
  }, [loadObservations, loadResults]);

  /* ── Run full analysis pipeline ── */
  const runPipeline = async () => {
    if (!startDate || !endDate) {
      setPipelineError('Select a date range first.');
      return;
    }
    setPipelineRunning(true);
    setPipelineError('');
    setPipelineDone(false);
    setError('');

    try {
      // Step 1: Feature Extraction
      setPipelineStep(0);
      const featRes = await featureAPI.extract(projectId, startDate, endDate);
      setFeatures(featRes.data?.features ?? null);

      // Step 2: Verification
      setPipelineStep(1);
      const verRes = await verificationAPI.verify(projectId, startDate, endDate);
      setVerification(verRes.data ?? null);

      // Step 3: ML Scoring
      setPipelineStep(2);
      try {
        const mlRes = await mlAPI.score(projectId, startDate, endDate);
        setMlResult(mlRes.data ?? null);
      } catch (mlErr) {
        // ML scoring can fail if models aren't trained — don't block
        console.warn('ML scoring skipped:', mlErr);
        setMlResult(null);
      }

      setPipelineStep(3);
      setPipelineDone(true);
    } catch (err) {
      setPipelineError(extractError(err, 'Analysis pipeline failed.'));
    } finally {
      setPipelineRunning(false);
    }
  };

  /* ── Charts ── */

  // Clamp vegetation index values to valid physical range
  const clamp = (v) => (v != null && v >= -0.2 && v <= 1.0 ? v : null);

  // Filter observations with valid NDVI, sorted by date
  const validObs = observations
    .filter((o) => clamp(o.ndvi) != null)
    .sort((a, b) => (a.observation_date > b.observation_date ? 1 : -1));

  // NDVI time series from observations
  const ndviTimeSeriesData =
    validObs.length > 0
      ? {
          labels: validObs.map((o) => o.observation_date),
          datasets: [
            {
              label: 'NDVI',
              data: validObs.map((o) => clamp(o.ndvi)),
              borderColor: '#22c55e',
              backgroundColor: 'rgba(34,197,94,0.12)',
              fill: true,
              tension: 0.35,
              pointRadius: 2.5,
              pointHoverRadius: 5,
              borderWidth: 2.5,
            },
            ...(validObs.some((o) => clamp(o.evi) != null)
              ? [
                  {
                    label: 'EVI',
                    data: validObs.map((o) => clamp(o.evi)),
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245,158,11,0.08)',
                    fill: false,
                    tension: 0.35,
                    pointRadius: 2.5,
                    pointHoverRadius: 5,
                    borderWidth: 2.5,
                    borderDash: [6, 3],
                  },
                ]
              : []),
          ],
        }
      : null;

  // Features bar chart
  const ndviBarData = features?.ndvi_stats
    ? {
        labels: ['Mean', 'Std', 'Min', 'Max', 'Median'],
        datasets: [
          {
            label: 'NDVI Stats',
            data: [
              features.ndvi_stats.mean,
              features.ndvi_stats.std,
              features.ndvi_stats.min,
              features.ndvi_stats.max,
              features.ndvi_stats.median,
            ],
            backgroundColor: [
              'rgba(34,197,94,0.7)',
              'rgba(14,165,233,0.7)',
              'rgba(239,68,68,0.7)',
              'rgba(34,197,94,0.9)',
              'rgba(245,158,11,0.7)',
            ],
            borderRadius: 4,
          },
        ],
      }
    : null;

  // Verification doughnut
  const confidenceDoughnut =
    verification?.confidence_score != null
      ? {
          labels: ['Confidence', 'Remaining'],
          datasets: [
            {
              data: [
                verification.confidence_score,
                100 - verification.confidence_score,
              ],
              backgroundColor: ['#22c55e', 'rgba(255,255,255,0.08)'],
              borderWidth: 0,
            },
          ],
        }
      : null;

  const hasResults = features || verification || mlResult;
  const isLoading = obsLoading || resultsLoading;

  if (isLoading) return <LinearProgress />;

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* ═══════════ SATELLITE IMAGES ═══════════ */}
      {observations.length > 0 && (
        <Card variant="outlined" sx={{ mb: 2 }}>
          <CardHeader
            avatar={<SatelliteAltIcon sx={{ color: 'primary.main' }} />}
            title="Satellite Images"
            subheader={(() => {
              const dates = validObs.map((o) => o.observation_date).filter(Boolean);
              if (dates.length === 0) return `${observations.length} images captured`;
              const first = dates[0];
              const last = dates[dates.length - 1];
              return `${observations.length} images captured from ${first} to ${last}`;
            })()}
          />
          <CardContent>
            {ndviTimeSeriesData && (
              <Box sx={{ height: 280 }}>
                <Line
                  ref={chartRef}
                  data={{
                    ...ndviTimeSeriesData,
                    datasets: ndviTimeSeriesData.datasets.map((ds) => ({
                      ...ds,
                      pointRadius: 4,
                      pointHoverRadius: 8,
                      pointHitRadius: 12,
                      pointBackgroundColor: ds.label === 'EVI' ? '#f59e0b' : '#22c55e',
                      pointBorderColor: ds.label === 'EVI' ? '#f59e0b' : '#22c55e',
                      ...(selectedObs
                        ? {
                            pointRadius: validObs.map((o) =>
                              o.observation_date === selectedObs.observation_date ? 8 : 4,
                            ),
                            pointBorderWidth: validObs.map((o) =>
                              o.observation_date === selectedObs.observation_date ? 3 : 1,
                            ),
                            pointBorderColor: validObs.map((o) =>
                              o.observation_date === selectedObs.observation_date
                                ? '#fff'
                                : ds.label === 'EVI'
                                  ? '#f59e0b'
                                  : '#22c55e',
                            ),
                          }
                        : {}),
                    })),
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    onClick: (_event, elements) => {
                      if (elements.length > 0) {
                        const idx = elements[0].index;
                        setSelectedObs(validObs[idx]);
                      }
                    },
                    onHover: (event, elements) => {
                      const canvas = event?.native?.target;
                      if (canvas) canvas.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                    },
                    plugins: {
                      legend: {
                        labels: {
                          color: 'rgba(255,255,255,0.8)',
                          usePointStyle: true,
                          pointStyle: 'circle',
                          padding: 16,
                        },
                      },
                      tooltip: {
                        backgroundColor: 'rgba(15,17,23,0.95)',
                        borderColor: 'rgba(34,197,94,0.3)',
                        borderWidth: 1,
                        titleColor: '#fff',
                        bodyColor: 'rgba(255,255,255,0.8)',
                        titleFont: { size: 13, weight: 'bold' },
                        bodyFont: { size: 12 },
                        padding: 12,
                        callbacks: {
                          title: (items) => {
                            const d = items[0]?.label;
                            return d ? `📅 ${d}` : '';
                          },
                          afterTitle: () => 'Click to view details',
                          label: (ctx) =>
                            ` ${ctx.dataset.label}: ${ctx.parsed.y != null ? ctx.parsed.y.toFixed(3) : '—'}`,
                          afterBody: (items) => {
                            const idx = items[0]?.dataIndex;
                            if (idx == null) return '';
                            const obs = validObs[idx];
                            if (!obs) return '';
                            const parts = [];
                            if (obs.cloud_cover_percent != null)
                              parts.push(`☁️ Cloud: ${obs.cloud_cover_percent.toFixed(1)}%`);
                            if (obs.data_source) parts.push(`📡 ${obs.data_source}`);
                            return parts.length > 0 ? '\n' + parts.join('\n') : '';
                          },
                        },
                      },
                    },
                    scales: {
                      x: {
                        ticks: {
                          color: 'rgba(255,255,255,0.5)',
                          maxTicksLimit: 10,
                          maxRotation: 45,
                          font: { size: 11 },
                        },
                        grid: { color: 'rgba(255,255,255,0.04)' },
                      },
                      y: {
                        min: 0,
                        max: 1,
                        ticks: {
                          color: 'rgba(255,255,255,0.5)',
                          stepSize: 0.2,
                          font: { size: 11 },
                        },
                        grid: { color: 'rgba(255,255,255,0.06)' },
                        title: {
                          display: true,
                          text: 'Vegetation Health',
                          color: 'rgba(255,255,255,0.4)',
                          font: { size: 11 },
                        },
                      },
                    },
                  }}
                />
              </Box>
            )}

            {/* Helpful hint */}
            <Typography
              variant="caption"
              sx={{ display: 'block', mt: 0.5, textAlign: 'center', color: 'text.disabled' }}
            >
              Click any point on the chart or any card below to view image details
            </Typography>

            {/* Quick stats row */}
            <Grid container spacing={2} sx={{ mt: 1 }}>
              {(() => {
                const ndvis = validObs
                  .map((o) => clamp(o.ndvi))
                  .filter((v) => v != null);
                const evis = validObs
                  .map((o) => clamp(o.evi))
                  .filter((v) => v != null);
                if (ndvis.length === 0) return null;
                const avg = ndvis.reduce((a, b) => a + b, 0) / ndvis.length;
                const min = Math.min(...ndvis);
                const max = Math.max(...ndvis);
                const avgEvi =
                  evis.length > 0
                    ? evis.reduce((a, b) => a + b, 0) / evis.length
                    : null;
                return (
                  <>
                    <Grid item xs={6} sm={2.4}>
                      <Typography variant="caption" color="text.secondary">
                        Total Images
                      </Typography>
                      <Typography variant="h6">{observations.length}</Typography>
                    </Grid>
                    <Grid item xs={6} sm={2.4}>
                      <Typography variant="caption" color="text.secondary">
                        Avg NDVI
                      </Typography>
                      <Typography variant="h6" color="primary.main">
                        {fmt(avg, 3)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={2.4}>
                      <Typography variant="caption" color="text.secondary">
                        Min NDVI
                      </Typography>
                      <Typography variant="h6" sx={{ color: '#ef4444' }}>
                        {fmt(min, 3)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={2.4}>
                      <Typography variant="caption" color="text.secondary">
                        Max NDVI
                      </Typography>
                      <Typography variant="h6" sx={{ color: '#22c55e' }}>
                        {fmt(max, 3)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={2.4}>
                      <Typography variant="caption" color="text.secondary">
                        Avg EVI
                      </Typography>
                      <Typography variant="h6" sx={{ color: '#f59e0b' }}>
                        {avgEvi != null ? fmt(avgEvi, 3) : '—'}
                      </Typography>
                    </Grid>
                  </>
                );
              })()}
            </Grid>

            {/* ── Image Gallery ── */}
            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
              All Captured Images ({validObs.length})
            </Typography>
            <Box
              sx={{
                display: 'flex',
                gap: 1.5,
                overflowX: 'auto',
                pb: 1.5,
                '&::-webkit-scrollbar': { height: 6 },
                '&::-webkit-scrollbar-thumb': {
                  background: 'rgba(255,255,255,0.15)',
                  borderRadius: 3,
                },
              }}
            >
              {validObs.map((obs) => {
                const isSelected =
                  selectedObs?.observation_date === obs.observation_date;
                // NDVI → green health bar (0 to 1)
                const ndviPct = Math.max(0, Math.min(100, (clamp(obs.ndvi) ?? 0) * 100));
                const health = ndviHealth(clamp(obs.ndvi));
                return (
                  <Box
                    key={obs.id || obs.observation_date}
                    onClick={() => setSelectedObs(isSelected ? null : obs)}
                    sx={{
                      flexShrink: 0,
                      width: 155,
                      p: 1.5,
                      borderRadius: 2,
                      cursor: 'pointer',
                      border: isSelected
                        ? '2px solid #22c55e'
                        : '1px solid rgba(255,255,255,0.08)',
                      background: isSelected
                        ? 'rgba(34,197,94,0.08)'
                        : 'rgba(255,255,255,0.02)',
                      transition: 'all 0.2s',
                      '&:hover': {
                        background: 'rgba(34,197,94,0.06)',
                        borderColor: 'rgba(34,197,94,0.3)',
                        transform: 'translateY(-2px)',
                      },
                    }}
                  >
                    {/* Date */}
                    <Typography
                      variant="caption"
                      sx={{ fontWeight: 600, color: 'rgba(255,255,255,0.7)', display: 'block' }}
                    >
                      {obs.observation_date}
                    </Typography>

                    {/* Health emoji + label */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      <Typography sx={{ fontSize: 16, lineHeight: 1 }}>{health.emoji}</Typography>
                      <Typography variant="caption" sx={{ color: health.color, fontWeight: 600 }}>
                        {health.label}
                      </Typography>
                    </Box>

                    {/* NDVI value + health bar */}
                    <Typography variant="body2" sx={{ fontWeight: 700, color: health.color, mt: 0.5 }}>
                      {clamp(obs.ndvi)?.toFixed(3) ?? '—'}
                    </Typography>
                    <Box
                      sx={{
                        height: 4,
                        borderRadius: 2,
                        mt: 0.5,
                        background: 'rgba(255,255,255,0.06)',
                        overflow: 'hidden',
                      }}
                    >
                      <Box
                        sx={{
                          width: `${ndviPct}%`,
                          height: '100%',
                          background: health.color,
                          borderRadius: 2,
                          transition: 'width 0.3s',
                        }}
                      />
                    </Box>

                    {/* EVI (if available) */}
                    {clamp(obs.evi) != null && (
                      <Typography
                        variant="caption"
                        sx={{ color: '#f59e0b', display: 'block', mt: 0.5 }}
                      >
                        EVI {clamp(obs.evi).toFixed(3)}
                      </Typography>
                    )}

                    {/* Cloud cover */}
                    {obs.cloud_cover_percent != null && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.3, mt: 0.5 }}>
                        <CloudIcon sx={{ fontSize: 12, color: 'rgba(255,255,255,0.3)' }} />
                        <Typography variant="caption" color="text.disabled">
                          {obs.cloud_cover_percent.toFixed(0)}%
                        </Typography>
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* ── Selected observation detail dialog ── */}
      <Dialog
        open={!!selectedObs}
        onClose={() => setSelectedObs(null)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            background: '#1a1d24',
            border: '1px solid rgba(34,197,94,0.2)',
            borderRadius: 3,
          },
        }}
      >
        {selectedObs && (() => {
          const health = ndviHealth(clamp(selectedObs.ndvi));
          const ndviVal = clamp(selectedObs.ndvi);
          const eviVal = clamp(selectedObs.evi);
          const cloudPct = selectedObs.cloud_cover_percent;
          const cloudGood = cloudPct != null && cloudPct < 20;
          const cloudBad = cloudPct != null && cloudPct >= 40;

          return (
            <>
              <DialogTitle sx={{ pb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 1 }}>
                      {friendlySource(selectedObs.data_source)} · {selectedObs.observation_date}
                    </Typography>
                    {/* Big health verdict */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 0.5 }}>
                      <Typography sx={{ fontSize: 36 }}>{health.emoji}</Typography>
                      <Box>
                        <Typography variant="h5" sx={{ fontWeight: 700, color: health.color }}>
                          {health.label}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 340 }}>
                          {health.desc}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                  <IconButton onClick={() => setSelectedObs(null)} size="small" sx={{ mt: -0.5 }}>
                    <CloseIcon />
                  </IconButton>
                </Box>
              </DialogTitle>
              <DialogContent>
                {/* ── SATELLITE IMAGE ── */}
                <Box
                  sx={{
                    mb: 2,
                    borderRadius: 2,
                    overflow: 'hidden',
                    background: '#000',
                    position: 'relative',
                    minHeight: 200,
                  }}
                >
                  {thumbLoading && (
                    <Box
                      sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        py: 5,
                        gap: 1.5,
                      }}
                    >
                      <CircularProgress size={36} sx={{ color: '#22c55e' }} />
                      <Typography variant="body2" color="text.secondary">
                        Loading satellite image from Google Earth Engine...
                      </Typography>
                    </Box>
                  )}

                  {thumbError && !thumbLoading && (
                    <Box sx={{ textAlign: 'center', py: 4, px: 2 }}>
                      <SatelliteAltIcon sx={{ fontSize: 40, color: 'rgba(255,255,255,0.15)', mb: 1 }} />
                      <Typography variant="body2" color="text.secondary">
                        {thumbError}
                      </Typography>
                    </Box>
                  )}

                  {thumbData?.url && !thumbLoading && (
                    <>
                      <Box
                        component="img"
                        src={showNdviImage && thumbData.ndvi_url ? thumbData.ndvi_url : thumbData.url}
                        alt={`Satellite view — ${selectedObs.observation_date}`}
                        sx={{
                          width: '100%',
                          display: 'block',
                          cursor: 'pointer',
                        }}
                        onClick={() => setShowNdviImage(!showNdviImage)}
                      />
                      {/* Toggle RGB / NDVI */}
                      <Box
                        sx={{
                          position: 'absolute',
                          bottom: 8,
                          right: 8,
                          display: 'flex',
                          gap: 0.5,
                        }}
                      >
                        <Chip
                          label="True Color"
                          size="small"
                          onClick={() => setShowNdviImage(false)}
                          sx={{
                            background: !showNdviImage ? '#22c55e' : 'rgba(0,0,0,0.6)',
                            color: '#fff',
                            fontWeight: 600,
                            fontSize: 11,
                            cursor: 'pointer',
                            backdropFilter: 'blur(4px)',
                          }}
                        />
                        {thumbData.ndvi_url && (
                          <Chip
                            label="Vegetation Map"
                            size="small"
                            onClick={() => setShowNdviImage(true)}
                            sx={{
                              background: showNdviImage ? '#22c55e' : 'rgba(0,0,0,0.6)',
                              color: '#fff',
                              fontWeight: 600,
                              fontSize: 11,
                              cursor: 'pointer',
                              backdropFilter: 'blur(4px)',
                            }}
                          />
                        )}
                      </Box>
                      <Typography
                        variant="caption"
                        sx={{
                          position: 'absolute',
                          bottom: 8,
                          left: 8,
                          color: 'rgba(255,255,255,0.6)',
                          background: 'rgba(0,0,0,0.5)',
                          px: 1,
                          py: 0.3,
                          borderRadius: 1,
                          backdropFilter: 'blur(4px)',
                          fontSize: 10,
                        }}
                      >
                        {showNdviImage ? 'NDVI false-color (red=bare, green=vegetation)' : 'True color satellite image'}
                        &nbsp;· Click to toggle
                      </Typography>
                    </>
                  )}
                </Box>

                {/* Health scale bar */}
                <Box sx={{ mb: 3 }}>
                  <Box
                    sx={{
                      height: 12,
                      borderRadius: 6,
                      background:
                        'linear-gradient(to right, #ef4444 0%, #f97316 15%, #f59e0b 25%, #84cc16 40%, #22c55e 60%, #16a34a 100%)',
                      position: 'relative',
                    }}
                  >
                    {ndviVal != null && (
                      <Box
                        sx={{
                          position: 'absolute',
                          left: `${Math.max(2, Math.min(98, ndviVal * 100))}%`,
                          top: '50%',
                          transform: 'translate(-50%, -50%)',
                          width: 20,
                          height: 20,
                          borderRadius: '50%',
                          background: '#fff',
                          border: `3px solid ${health.color}`,
                          boxShadow: '0 0 8px rgba(0,0,0,0.5)',
                        }}
                      />
                    )}
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5, px: 0.5 }}>
                    <Typography variant="caption" color="text.disabled">0 — Bare</Typography>
                    <Typography variant="caption" color="text.disabled">0.5 — Moderate</Typography>
                    <Typography variant="caption" color="text.disabled">1.0 — Dense</Typography>
                  </Box>
                </Box>

                {/* Measurement cards */}
                <Grid container spacing={1.5}>
                  {/* NDVI - the main number */}
                  <Grid item xs={4}>
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        background: `${health.color}15`,
                        border: `1px solid ${health.color}40`,
                        textAlign: 'center',
                      }}
                    >
                      <Typography variant="h3" sx={{ color: health.color, fontWeight: 800, lineHeight: 1.1 }}>
                        {ndviVal?.toFixed(2) ?? '—'}
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                        NDVI score
                      </Typography>
                    </Box>
                  </Grid>

                  {/* EVI */}
                  <Grid item xs={4}>
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        background: eviVal != null ? 'rgba(245,158,11,0.1)' : 'rgba(255,255,255,0.03)',
                        border: eviVal != null ? '1px solid rgba(245,158,11,0.3)' : '1px solid rgba(255,255,255,0.08)',
                        textAlign: 'center',
                      }}
                    >
                      <Typography variant="h3" sx={{ color: eviVal != null ? '#f59e0b' : 'rgba(255,255,255,0.2)', fontWeight: 800, lineHeight: 1.1 }}>
                        {eviVal?.toFixed(2) ?? '—'}
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                        EVI score
                      </Typography>
                      {eviVal == null && (
                        <Typography variant="caption" display="block" sx={{ color: 'rgba(255,255,255,0.3)', fontSize: 10 }}>
                          Not available
                        </Typography>
                      )}
                    </Box>
                  </Grid>

                  {/* Cloud */}
                  <Grid item xs={4}>
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        background: cloudBad ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.03)',
                        border: cloudBad ? '1px solid rgba(239,68,68,0.2)' : '1px solid rgba(255,255,255,0.08)',
                        textAlign: 'center',
                      }}
                    >
                      <Typography variant="h3" sx={{ fontWeight: 800, lineHeight: 1.1, color: cloudBad ? '#ef4444' : cloudGood ? '#22c55e' : 'rgba(255,255,255,0.7)' }}>
                        {cloudPct != null ? `${cloudPct.toFixed(0)}%` : '—'}
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                        Cloud cover
                      </Typography>
                      {cloudGood && (
                        <Typography variant="caption" display="block" sx={{ color: '#22c55e', fontSize: 10 }}>
                          ✓ Clear sky
                        </Typography>
                      )}
                      {cloudBad && (
                        <Typography variant="caption" display="block" sx={{ color: '#ef4444', fontSize: 10 }}>
                          ⚠ Partially obscured
                        </Typography>
                      )}
                    </Box>
                  </Grid>
                </Grid>

                {/* Additional details - collapsible-style section */}
                <Box sx={{ mt: 2.5, p: 1.5, borderRadius: 2, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>
                    Technical Details
                  </Typography>
                  <Grid container spacing={1} sx={{ mt: 0.5 }}>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.disabled">Satellite</Typography>
                      <Typography variant="body2">{friendlySource(selectedObs.data_source)}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.disabled">Pixels Analyzed</Typography>
                      <Typography variant="body2">
                        {selectedObs.ndvi_count != null ? selectedObs.ndvi_count.toLocaleString() : '—'}
                      </Typography>
                    </Grid>
                    {selectedObs.ndvi_std != null && (
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.disabled">NDVI Std Dev</Typography>
                        <Typography variant="body2">± {selectedObs.ndvi_std.toFixed(4)}</Typography>
                      </Grid>
                    )}
                    {selectedObs.biomass_estimate != null && (
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.disabled">Biomass Estimate</Typography>
                        <Typography variant="body2" sx={{ color: '#22c55e', fontWeight: 600 }}>
                          {selectedObs.biomass_estimate.toFixed(2)} t/ha
                          {selectedObs.biomass_std != null && ` ± ${selectedObs.biomass_std.toFixed(2)}`}
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </Box>

                {/* What do these numbers mean? */}
                <Box sx={{ mt: 2, p: 1.5, borderRadius: 2, background: 'rgba(34,197,94,0.04)', border: '1px solid rgba(34,197,94,0.1)' }}>
                  <Typography variant="caption" sx={{ color: '#22c55e', fontWeight: 600 }}>
                    💡 What do these numbers mean?
                  </Typography>
                  <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                    <strong>NDVI</strong> (0–1) measures how green and alive the vegetation is. Higher = greener.&nbsp;
                    <strong>EVI</strong> is a refined version that works better in dense forests.&nbsp;
                    <strong>Cloud cover</strong> below 20% means you're getting a clear, reliable reading.
                  </Typography>
                </Box>
              </DialogContent>
            </>
          );
        })()}
      </Dialog>

      {observations.length === 0 && !hasResults && (
        <Alert severity="info" sx={{ mb: 2 }} icon={<SatelliteAltIcon />}>
          No satellite images yet. Go to the <strong>Monitoring</strong> tab and run a job
          to start capturing images from the satellite.
        </Alert>
      )}

      {/* ═══════════ ANALYSIS PIPELINE ═══════════ */}
      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardHeader
          title="Analysis Pipeline"
          subheader="Extract features, verify biomass signals, and run ML scoring"
          avatar={<ScienceIcon sx={{ color: 'primary.main' }} />}
        />
        <CardContent>
          {/* Date range */}
          <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
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
                size="large"
                onClick={runPipeline}
                disabled={pipelineRunning || !startDate || !endDate}
                startIcon={
                  pipelineRunning ? (
                    <CircularProgress size={18} color="inherit" />
                  ) : (
                    <ScienceIcon />
                  )
                }
              >
                {pipelineRunning ? 'Running…' : 'Run Full Analysis'}
              </Button>
            </Grid>
          </Grid>

          {/* Stepper */}
          {(pipelineRunning || pipelineDone || pipelineError) && (
            <Stepper
              activeStep={pipelineStep}
              alternativeLabel
              sx={{ mb: 2 }}
            >
              {PIPELINE_STEPS.map((label, idx) => {
                const isErr =
                  pipelineError && pipelineStep === idx && !pipelineDone;
                return (
                  <Step key={label} completed={pipelineStep > idx}>
                    <StepLabel
                      error={isErr}
                      StepIconComponent={
                        pipelineStep > idx
                          ? () => (
                              <CheckCircleIcon
                                sx={{ color: 'success.main', fontSize: 28 }}
                              />
                            )
                          : isErr
                            ? () => (
                                <ErrorIcon
                                  sx={{ color: 'error.main', fontSize: 28 }}
                                />
                              )
                            : undefined
                      }
                    >
                      {label}
                    </StepLabel>
                  </Step>
                );
              })}
            </Stepper>
          )}

          {pipelineError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {pipelineError}
            </Alert>
          )}

          {pipelineDone && (
            <Alert severity="success" variant="outlined">
              Analysis pipeline completed successfully!
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* ═══════════ ANALYSIS RESULTS ═══════════ */}
      {hasResults && (
        <Grid container spacing={2}>
          {/* ── Key Metrics ── */}
          {features && (
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardHeader title="Extracted Features" />
                <CardContent>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">
                        NDVI Mean
                      </Typography>
                      <Typography variant="h6">
                        {fmt(features.ndvi_stats?.mean)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">
                        Trend Slope
                      </Typography>
                      <Typography variant="h6">
                        {fmt(features.trend?.trend_slope, 4)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">
                        R²
                      </Typography>
                      <Typography variant="h6">
                        {fmt(features.trend?.r_squared)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">
                        Seasonal Amplitude
                      </Typography>
                      <Typography variant="h6">
                        {fmt(features.seasonality?.seasonal_amplitude)}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">
                        Total Observations
                      </Typography>
                      <Typography variant="h6">
                        {features.total_observations ?? '—'}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">
                        Clear Observations
                      </Typography>
                      <Typography variant="h6">
                        {features.clear_observations ?? '—'}
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* ── NDVI Bar Chart ── */}
          {ndviBarData && (
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardHeader title="NDVI Distribution" />
                <CardContent>
                  <Bar
                    data={ndviBarData}
                    options={{
                      responsive: true,
                      plugins: {
                        legend: { display: false },
                      },
                      scales: {
                        y: {
                          beginAtZero: true,
                          max: 1,
                          ticks: { color: 'rgba(255,255,255,0.5)' },
                          grid: { color: 'rgba(255,255,255,0.06)' },
                        },
                        x: {
                          ticks: { color: 'rgba(255,255,255,0.5)' },
                          grid: { display: false },
                        },
                      },
                    }}
                  />
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* ── Verification ── */}
          {verification && (
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardHeader
                  title="Verification"
                  action={
                    <Chip
                      label={verification.overall_status}
                      color={
                        STATUS_CHIP[verification.overall_status] || 'default'
                      }
                      size="small"
                    />
                  }
                />
                <CardContent>
                  {confidenceDoughnut && (
                    <Box sx={{ maxWidth: 180, mx: 'auto', mb: 2 }}>
                      <Doughnut
                        data={confidenceDoughnut}
                        options={{
                          cutout: '72%',
                          plugins: {
                            legend: { display: false },
                            tooltip: { enabled: false },
                          },
                        }}
                      />
                      <Typography
                        sx={{ textAlign: 'center', mt: 1 }}
                        variant="h5"
                        color="primary.main"
                      >
                        {fmt(verification.confidence_score, 0)}%
                      </Typography>
                    </Box>
                  )}

                  {verification.verification_flags?.length > 0 && (
                    <Box>
                      <Typography variant="subtitle2" gutterBottom>
                        Flags (
                        {verification.flag_count ??
                          verification.verification_flags.length}
                        )
                      </Typography>
                      {verification.verification_flags.map((flag, idx) => (
                        <Alert
                          key={idx}
                          severity={
                            flag.risk_level === 'critical'
                              ? 'error'
                              : flag.risk_level === 'high'
                                ? 'warning'
                                : 'info'
                          }
                          sx={{ mb: 1, py: 0 }}
                          variant="outlined"
                        >
                          <strong>{flag.rule_name}</strong> — {flag.description}
                        </Alert>
                      ))}
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* ── ML Scoring ── */}
          {mlResult?.scoring && (
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardHeader title="ML Scoring" />
                <CardContent>
                  {mlResult.scoring?.growth && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Growth Classification
                      </Typography>
                      <Chip
                        label={
                          mlResult.scoring.growth.prediction ||
                          mlResult.scoring.growth.classification
                        }
                        color={
                          ['significant_growth', 'healthy'].includes(
                            mlResult.scoring.growth.prediction ||
                              mlResult.scoring.growth.classification,
                          )
                            ? 'success'
                            : ['decline', 'stressed'].includes(
                                  mlResult.scoring.growth.prediction ||
                                    mlResult.scoring.growth.classification,
                                )
                              ? 'error'
                              : 'warning'
                        }
                        sx={{ mb: 1 }}
                      />
                      <Typography variant="body2" color="text.secondary">
                        Confidence:{' '}
                        {fmt(
                          mlResult.scoring.growth.confidence ??
                            mlResult.scoring.growth.confidence_score,
                        )}
                        %
                      </Typography>
                    </Box>
                  )}

                  {mlResult.scoring?.biomass && (
                    <Box>
                      <Typography variant="subtitle2" gutterBottom>
                        Biomass Estimate
                      </Typography>
                      <Typography variant="h5" color="primary.main">
                        {fmt(
                          mlResult.scoring.biomass.biomass_estimate ??
                            mlResult.scoring.biomass.estimated_biomass,
                        )}{' '}
                        t/ha
                      </Typography>
                    </Box>
                  )}

                  {!mlResult.scoring?.growth && !mlResult.scoring?.biomass && (
                    <Typography variant="body2" color="text.secondary">
                      Scoring data: {JSON.stringify(mlResult.scoring).slice(0, 200)}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* ML result without nested scoring key */}
          {mlResult && !mlResult.scoring && mlResult.growth && (
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardHeader title="ML Scoring" />
                <CardContent>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Growth Classification
                    </Typography>
                    <Chip
                      label={mlResult.growth.prediction || mlResult.growth.classification}
                      color="success"
                      sx={{ mb: 1 }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      Confidence:{' '}
                      {fmt(mlResult.growth.confidence ?? mlResult.growth.confidence_score)}%
                    </Typography>
                  </Box>
                  {mlResult.biomass && (
                    <Box>
                      <Typography variant="subtitle2" gutterBottom>
                        Biomass Estimate
                      </Typography>
                      <Typography variant="h5" color="primary.main">
                        {fmt(mlResult.biomass.biomass_estimate ?? mlResult.biomass.estimated_biomass)} t/ha
                      </Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>
      )}
    </Box>
  );
}

export default ResultsPanel;
