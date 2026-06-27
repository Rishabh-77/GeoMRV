import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItem,
  ListItemText,
  TextField,
  Typography,
} from '@mui/material';
import { evidenceAPI } from '../api/client';

function EvidenceDownload({ projectId }) {
  const [open, setOpen] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [generating, setGenerating] = useState(false);
  const [packageId, setPackageId] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');

  /* ── Generate ── */
  const handleGenerate = async () => {
    if (!startDate || !endDate) return;
    setGenerating(true);
    setError('');
    setPackageId('');
    try {
      const res = await evidenceAPI.generate(projectId, startDate, endDate);
      setPackageId(res.data?.package_id || res.data?.id || '');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Evidence generation failed.');
    } finally {
      setGenerating(false);
    }
  };

  /* ── Download ── */
  const handleDownload = async () => {
    if (!packageId) return;
    setDownloading(true);
    try {
      const res = await evidenceAPI.download(packageId);
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `evidence_${packageId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Download failed.');
    } finally {
      setDownloading(false);
    }
  };

  /* ── Reset ── */
  const handleClose = () => {
    setOpen(false);
    setError('');
    setPackageId('');
    setStartDate('');
    setEndDate('');
  };

  return (
    <Card variant="outlined">
      <CardHeader title="Evidence Packages" />
      <CardContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Generate audit-ready evidence packages with PDF reports, processing lineage, and
          verification results.
        </Typography>

        <Button variant="contained" onClick={() => setOpen(true)}>
          Generate Evidence Package
        </Button>

        {/* ── Dialog ── */}
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
          <DialogTitle>Generate Evidence Package</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', gap: 2, mt: 1, mb: 2 }}>
              <TextField
                type="date"
                label="Analysis Start"
                size="small"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
                fullWidth
              />
              <TextField
                type="date"
                label="Analysis End"
                size="small"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
                fullWidth
              />
            </Box>

            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            {packageId && (
              <Alert severity="success" sx={{ mb: 2 }}>
                Evidence package generated successfully.
                <List dense disablePadding>
                  <ListItem disableGutters>
                    <ListItemText
                      primary="Package ID"
                      secondary={packageId}
                    />
                  </ListItem>
                </List>
              </Alert>
            )}
          </DialogContent>

          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={handleClose}>Cancel</Button>

            {!packageId && (
              <Button
                variant="contained"
                onClick={handleGenerate}
                disabled={!startDate || !endDate || generating}
                startIcon={generating ? <CircularProgress size={16} /> : undefined}
              >
                {generating ? 'Generating…' : 'Generate'}
              </Button>
            )}

            {packageId && (
              <Button
                variant="contained"
                color="success"
                onClick={handleDownload}
                disabled={downloading}
                startIcon={downloading ? <CircularProgress size={16} /> : undefined}
              >
                {downloading ? 'Downloading…' : 'Download PDF'}
              </Button>
            )}
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
}

export default EvidenceDownload;
