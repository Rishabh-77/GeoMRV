# Phase 4: Frontend & Integration (Weeks 12–13)

**Duration:** 2 weeks  
**Goal:** Build React dashboard and integrate all backend components  
**Deliverable:** Functional web interface for project management and result viewing

---

## 📊 Phase Overview

Phase 4 brings the system to life with a user-facing dashboard. The frontend:
- Manages project boundaries (upload, view, edit)
- Tracks monitoring job status
- Displays evidence and results
- Provides timelapse previews for visual inspection (Sentinel-2 via GEE exports)
- Downloads reports
- Provides audit trail visibility

### Success Metrics
- Dashboard deployed on Azure Static Web Apps
- All project operations functional
- Real-time job status updates
- Evidence packages downloadable
- Timelapse preview viewable per project
- End-to-end system operational

---

## 🎯 Tasks Breakdown

### Task 4.1: React Dashboard Setup (Days 1–3)

**Objective:** Initialize frontend project and core components

**Steps:**

1. **Create React App**
   ```bash
   npx create-react-app frontend
   cd frontend
   npm install axios react-router-dom leaflet react-leaflet chart.js react-chartjs-2 @mui/material @emotion/react @emotion/styled
   ```

2. **Create Project Structure**
   ```
   frontend/
   ├── src/
   │   ├── components/
   │   │   ├── ProjectForm.jsx
   │   │   ├── BoundaryViewer.jsx
   │   │   ├── JobStatus.jsx
   │   │   ├── ResultsPanel.jsx
    │   │   ├── TimelapsePlayer.jsx
   │   │   └── EvidenceDownload.jsx
   │   ├── pages/
   │   │   ├── Dashboard.jsx
   │   │   ├── ProjectDetail.jsx
   │   │   └── EvidencePackage.jsx
   │   ├── api/
   │   │   └── client.js
   │   ├── App.jsx
   │   └── App.css
   ```

3. **Create API Client**
   ```javascript
   // frontend/src/api/client.js
   import axios from 'axios';
   
   const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
   
   export const apiClient = axios.create({
       baseURL: API_BASE,
       headers: {
           'Content-Type': 'application/json'
       }
   });
   
   export const projectAPI = {
       list: () => apiClient.get('/projects'),
       create: (data) => apiClient.post('/projects', data),
       get: (id) => apiClient.get(`/projects/${id}`),
       uploadBoundary: (id, file) => {
           const formData = new FormData();
           formData.append('file', file);
           return apiClient.post(`/projects/${id}/upload-boundary`, formData);
       }
   };
   
   export const jobAPI = {
       create: (data) => apiClient.post('/jobs', data),
       get: (id) => apiClient.get(`/jobs/${id}`),
       list: (projectId) => apiClient.get(`/jobs?project_id=${projectId}`)
   };
   
   export const evidenceAPI = {
       generate: (projectId, startDate, endDate) => 
           apiClient.post(`/evidence/${projectId}/generate`, { startDate, endDate }),
       download: (packageId) => apiClient.get(`/evidence/${packageId}/download`)
   };

   // Returns a signed URL (SAS) or direct URL to an MP4 timelapse stored in Blob.
   // Expected backend route: GET /projects/:id/timelapse?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
   export const timelapseAPI = {
       getUrl: (projectId, startDate, endDate) =>
           apiClient.get(`/projects/${projectId}/timelapse`, { params: { startDate, endDate } })
   };
   ```

4. **Create Dashboard Layout**
   ```javascript
   // frontend/src/pages/Dashboard.jsx
   import React, { useState, useEffect } from 'react';
   import { projectAPI } from '../api/client';
   import { Button, Container, Card, Grid } from '@mui/material';
   import ProjectForm from '../components/ProjectForm';
   
   function Dashboard() {
       const [projects, setProjects] = useState([]);
       const [showForm, setShowForm] = useState(false);
       
       useEffect(() => {
           loadProjects();
       }, []);
       
       const loadProjects = async () => {
           try {
               const response = await projectAPI.list();
               setProjects(response.data);
           } catch (error) {
               console.error('Error loading projects:', error);
           }
       };
       
       const handleCreateProject = async (data) => {
           try {
               await projectAPI.create(data);
               loadProjects();
               setShowForm(false);
           } catch (error) {
               console.error('Error creating project:', error);
           }
       };
       
       return (
           <Container maxWidth="lg" style={{ marginTop: '2rem' }}>
               <h1>GeoMRV Dashboard</h1>
               
               <Button 
                   variant="contained" 
                   color="primary"
                   onClick={() => setShowForm(!showForm)}
                   style={{ marginBottom: '2rem' }}
               >
                   {showForm ? 'Cancel' : 'New Project'}
               </Button>
               
               {showForm && <ProjectForm onSubmit={handleCreateProject} />}
               
               <Grid container spacing={2}>
                   {projects.map(project => (
                       <Grid item xs={12} sm={6} md={4} key={project.id}>
                           <Card style={{ padding: '1rem', cursor: 'pointer' }}>
                               <h3>{project.name}</h3>
                               <p>{project.description}</p>
                               <p><strong>Type:</strong> {project.project_type}</p>
                               <p><strong>Area:</strong> {project.total_area_ha} ha</p>
                           </Card>
                       </Grid>
                   ))}
               </Grid>
           </Container>
       );
   }
   
   export default Dashboard;
   ```

**Deliverables:**
- [ ] React app created
- [ ] API client implemented
- [ ] Dashboard layout basic structure
- [ ] Project list displaying
- [ ] Routing configured

**Files to Create:**
- `frontend/src/api/client.js`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/components/ProjectForm.jsx`

---

### Task 4.2: Core Components (Days 3–7)

**Objective:** Build key dashboard components

**Steps:**

1. **Boundary Upload & Viewer**
   ```javascript
   // frontend/src/components/BoundaryViewer.jsx
   import React, { useState } from 'react';
   import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
   import 'leaflet/dist/leaflet.css';
   import { projectAPI } from '../api/client';
   
   function BoundaryViewer({ projectId, onBoundaryLoaded }) {
       const [geoData, setGeoData] = useState(null);
       const [loading, setLoading] = useState(false);
       
       const handleFileUpload = async (event) => {
           const file = event.target.files[0];
           if (!file) return;
           
           setLoading(true);
           try {
               await projectAPI.uploadBoundary(projectId, file);
               // Load GeoJSON
               const reader = new FileReader();
               reader.onload = (e) => {
                   setGeoData(JSON.parse(e.target.result));
                   onBoundaryLoaded?.();
               };
               reader.readAsText(file);
           } catch (error) {
               console.error('Upload error:', error);
           }
           setLoading(false);
       };
       
       return (
           <div>
               <input 
                   type="file" 
                   accept=".geojson,.json,.zip"
                   onChange={handleFileUpload}
                   disabled={loading}
               />
               
               {geoData && (
                   <MapContainer center={[20, 78]} zoom={4} style={{ height: '400px' }}>
                       <TileLayer
                           url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                           attribution='&copy; OpenStreetMap'
                       />
                       <GeoJSON data={geoData} />
                   </MapContainer>
               )}
           </div>
       );
   }
   
   export default BoundaryViewer;
   ```

2. **Job Status Tracker**
   ```javascript
   // frontend/src/components/JobStatus.jsx
   import React, { useState, useEffect } from 'react';
   import { jobAPI } from '../api/client';
   import { LinearProgress, Alert } from '@mui/material';
   
   function JobStatus({ projectId, jobId }) {
       const [job, setJob] = useState(null);
       const [loading, setLoading] = useState(true);
       
       useEffect(() => {
           const pollJob = async () => {
               try {
                   const response = await jobAPI.get(jobId);
                   setJob(response.data);
                   setLoading(false);
               } catch (error) {
                   console.error('Error fetching job:', error);
               }
           };
           
           pollJob();
           const interval = setInterval(pollJob, 2000);
           return () => clearInterval(interval);
       }, [jobId]);
       
       if (loading) return <LinearProgress />;
       
       return (
           <div>
               <h4>Job Status: {job.status}</h4>
               {job.status === 'running' && <LinearProgress />}
               {job.status === 'completed' && (
                   <Alert severity="success">Job completed successfully</Alert>
               )}
               {job.status === 'failed' && (
                   <Alert severity="error">{job.error_message}</Alert>
               )}
           </div>
       );
   }
   
   export default JobStatus;
   ```

3. **Results Panel**
   ```javascript
   // frontend/src/components/ResultsPanel.jsx
   import React, { useState, useEffect } from 'react';
   import { Card, Grid, Box } from '@mui/material';
   import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
   
   function ResultsPanel({ features }) {
       if (!features) return <p>No results available</p>;
       
       const { ndvi_stats, trend, seasonality } = features;
       
       const monthlyData = [
           { month: 'Jan', ndvi: 0.3 },
           { month: 'Feb', ndvi: 0.35 },
           // ... would be populated from actual data
       ];
       
       return (
           <Grid container spacing={2}>
               <Grid item xs={12}>
                   <Card style={{ padding: '1rem' }}>
                       <h3>Key Metrics</h3>
                       <Grid container>
                           <Grid item xs={6}>
                               <p><strong>NDVI Mean:</strong> {ndvi_stats?.mean?.toFixed(2)}</p>
                               <p><strong>NDVI Std:</strong> {ndvi_stats?.std?.toFixed(2)}</p>
                           </Grid>
                           <Grid item xs={6}>
                               <p><strong>Trend Slope:</strong> {trend?.trend_slope?.toFixed(4)}</p>
                               <p><strong>R²:</strong> {trend?.r_squared?.toFixed(2)}</p>
                           </Grid>
                       </Grid>
                   </Card>
               </Grid>
               
               <Grid item xs={12}>
                   <Card style={{ padding: '1rem' }}>
                       <h3>Seasonal Pattern</h3>
                       <BarChart width={600} height={300} data={monthlyData}>
                           <CartesianGrid strokeDasharray="3 3" />
                           <XAxis dataKey="month" />
                           <YAxis />
                           <Tooltip />
                           <Bar dataKey="ndvi" fill="#8884d8" />
                       </BarChart>
                   </Card>
               </Grid>
           </Grid>
       );
   }
   
   export default ResultsPanel;
   ```

4. **Evidence Download**
   ```javascript
   // frontend/src/components/EvidenceDownload.jsx
   import React, { useState } from 'react';
   import { Button, Dialog, TextField, Alert } from '@mui/material';
   import { evidenceAPI } from '../api/client';
   
   function EvidenceDownload({ projectId }) {
       const [showDialog, setShowDialog] = useState(false);
       const [startDate, setStartDate] = useState('');
       const [endDate, setEndDate] = useState('');
       const [generating, setGenerating] = useState(false);
       const [packageId, setPackageId] = useState('');
       
       const handleGenerate = async () => {
           setGenerating(true);
           try {
               const response = await evidenceAPI.generate(projectId, startDate, endDate);
               setPackageId(response.data.package_id);
               Alert.success('Evidence package generated');
           } catch (error) {
               console.error('Generation error:', error);
           }
           setGenerating(false);
       };
       
       const handleDownload = async () => {
           try {
               const response = await evidenceAPI.download(packageId);
               // Create blob and download
               const url = window.URL.createObjectURL(new Blob([response.data]));
               const link = document.createElement('a');
               link.href = url;
               link.setAttribute('download', `evidence_${packageId}.pdf`);
               document.body.appendChild(link);
               link.click();
           } catch (error) {
               console.error('Download error:', error);
           }
       };
       
       return (
           <div>
               <Button variant="contained" onClick={() => setShowDialog(true)}>
                   Generate Evidence Package
               </Button>
               
               <Dialog open={showDialog} onClose={() => setShowDialog(false)}>
                   <Box style={{ padding: '2rem', minWidth: '400px' }}>
                       <h3>Generate Evidence Package</h3>
                       
                       <TextField
                           type="date"
                           label="Start Date"
                           value={startDate}
                           onChange={(e) => setStartDate(e.target.value)}
                           fullWidth
                           margin="normal"
                       />
                       
                       <TextField
                           type="date"
                           label="End Date"
                           value={endDate}
                           onChange={(e) => setEndDate(e.target.value)}
                           fullWidth
                           margin="normal"
                       />
                       
                       <Button 
                           onClick={handleGenerate}
                           disabled={!startDate || !endDate || generating}
                           variant="contained"
                           fullWidth
                           style={{ marginTop: '1rem' }}
                       >
                           {generating ? 'Generating...' : 'Generate'}
                       </Button>
                       
                       {packageId && (
                           <>
                               <Alert severity="success">Package generated</Alert>
                               <Button 
                                   onClick={handleDownload}
                                   variant="contained"
                                   color="success"
                                   fullWidth
                               >
                                   Download PDF
                               </Button>
                           </>
                       )}
                   </Box>
               </Dialog>
           </div>
       );
   }
   
   export default EvidenceDownload;
   ```

5. **Timelapse Player**

   Displays a per-project timelapse MP4 (typically exported from GEE and stored in Azure Blob). The backend should return a URL that the browser can stream.

   ```javascript
   // frontend/src/components/TimelapsePlayer.jsx
   import React, { useState } from 'react';
   import { Button, Card, Box, TextField, Alert } from '@mui/material';
   import { timelapseAPI } from '../api/client';

   function TimelapsePlayer({ projectId }) {
       const [startDate, setStartDate] = useState('');
       const [endDate, setEndDate] = useState('');
       const [loading, setLoading] = useState(false);
       const [videoUrl, setVideoUrl] = useState('');
       const [error, setError] = useState('');

       const loadTimelapse = async () => {
           setLoading(true);
           setError('');
           try {
               const response = await timelapseAPI.getUrl(projectId, startDate, endDate);
               setVideoUrl(response.data.url);
           } catch (e) {
               setError('Failed to load timelapse');
           }
           setLoading(false);
       };

       return (
           <Card style={{ padding: '1rem' }}>
               <h3>Timelapse Preview</h3>
               <Box style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                   <TextField
                       type="date"
                       label="Start Date"
                       value={startDate}
                       onChange={(e) => setStartDate(e.target.value)}
                   />
                   <TextField
                       type="date"
                       label="End Date"
                       value={endDate}
                       onChange={(e) => setEndDate(e.target.value)}
                   />
                   <Button
                       variant="contained"
                       onClick={loadTimelapse}
                       disabled={!startDate || !endDate || loading}
                   >
                       {loading ? 'Loading...' : 'Load Timelapse'}
                   </Button>
               </Box>

               {error && <Alert severity="error" style={{ marginTop: '1rem' }}>{error}</Alert>}

               {videoUrl && (
                   <Box style={{ marginTop: '1rem' }}>
                       <video src={videoUrl} controls style={{ width: '100%' }} />
                   </Box>
               )}
           </Card>
       );
   }

   export default TimelapsePlayer;
   ```

**Deliverables:**
- [ ] Boundary viewer with map
- [ ] Job status tracker with polling
- [ ] Results panel with charts
- [ ] Timelapse preview player (MP4)
- [ ] Evidence download dialog
- [ ] All components functional

**Files to Create:**
- `frontend/src/components/BoundaryViewer.jsx`
- `frontend/src/components/JobStatus.jsx`
- `frontend/src/components/ResultsPanel.jsx`
- `frontend/src/components/TimelapsePlayer.jsx`
- `frontend/src/components/EvidenceDownload.jsx`

---

### Task 4.3: Project Detail Page (Days 7–9)

**Objective:** Create detailed project view with all operations

**Steps:**

1. **Create Project Detail Page**
   ```javascript
   // frontend/src/pages/ProjectDetail.jsx
   import React, { useState, useEffect } from 'react';
   import { useParams } from 'react-router-dom';
   import { Container, Tabs, Tab, Box } from '@mui/material';
   import { projectAPI, jobAPI } from '../api/client';
   import BoundaryViewer from '../components/BoundaryViewer';
   import JobStatus from '../components/JobStatus';
   import ResultsPanel from '../components/ResultsPanel';
    import TimelapsePlayer from '../components/TimelapsePlayer';
   import EvidenceDownload from '../components/EvidenceDownload';
   
   function ProjectDetail() {
       const { projectId } = useParams();
       const [project, setProject] = useState(null);
       const [jobs, setJobs] = useState([]);
       const [currentJob, setCurrentJob] = useState(null);
       const [tabValue, setTabValue] = useState(0);
       
       useEffect(() => {
           loadProject();
           loadJobs();
       }, [projectId]);
       
       const loadProject = async () => {
           try {
               const response = await projectAPI.get(projectId);
               setProject(response.data);
           } catch (error) {
               console.error('Error loading project:', error);
           }
       };
       
       const loadJobs = async () => {
           try {
               const response = await jobAPI.list(projectId);
               setJobs(response.data);
               if (response.data.length > 0) {
                   setCurrentJob(response.data[0]);
               }
           } catch (error) {
               console.error('Error loading jobs:', error);
           }
       };
       
       if (!project) return <p>Loading...</p>;
       
       return (
           <Container maxWidth="lg" style={{ marginTop: '2rem' }}>
               <h1>{project.name}</h1>
               <p>{project.description}</p>
               
              <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
                  <Tab label="Boundary" />
                  <Tab label="Monitoring" />
                  <Tab label="Results" />
                  <Tab label="Timelapse" />
                  <Tab label="Evidence" />
              </Tabs>
               
               <Box style={{ marginTop: '2rem' }}>
                   {tabValue === 0 && <BoundaryViewer projectId={projectId} />}
                   
                   {tabValue === 1 && (
                       <div>
                           <h3>Monitoring Jobs</h3>
                           {currentJob && <JobStatus projectId={projectId} jobId={currentJob.id} />}
                       </div>
                   )}
                   
                   {tabValue === 2 && <ResultsPanel features={currentJob?.features} />}

                  {tabValue === 3 && <TimelapsePlayer projectId={projectId} />}
                  
                  {tabValue === 4 && <EvidenceDownload projectId={projectId} />}
               </Box>
           </Container>
       );
   }
   
   export default ProjectDetail;
   ```

**Deliverables:**
- [ ] Project detail page working
- [ ] All tabs functional
- [ ] Job history displayed
- [ ] Results viewable

---

### Task 4.4: Azure Static Web Apps Deployment (Days 9–11)

**Objective:** Deploy frontend to Azure

**Steps:**

1. **Create Build Configuration**
   ```yaml
   # frontend/.github/workflows/azure-static-web-apps-deploy.yml
   name: Azure Static Web Apps CI/CD
   
   on:
     push:
       branches:
         - main
     pull_request:
       types: [opened, synchronize, reopened, closed]
       branches:
         - main
   
   jobs:
     build_and_deploy_job:
       runs-on: ubuntu-latest
       name: Build and Deploy Job
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Build
         run: |
           cd frontend
           npm ci
           npm run build
       
       - name: Deploy
         uses: Azure/static-web-apps-deploy@v1
         with:
           azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_TOKEN }}
           repo_token: ${{ secrets.GITHUB_TOKEN }}
           action: "upload"
           app_location: "/frontend/build"
           output_location: ""
   ```

2. **Set Environment Variables**
   ```bash
   # frontend/.env.production
   REACT_APP_API_URL=https://geomrv-api.azurewebsites.net/api/v1
   ```

3. **Deploy to Azure**
   ```bash
   # Push to GitHub and GitHub Actions will deploy automatically
   git add .
   git commit -m "Deploy frontend"
   git push origin main
   ```

**Deliverables:**
- [ ] GitHub Actions workflow configured
- [ ] Build succeeds
- [ ] Deployed to Azure Static Web Apps
- [ ] Accessible via public URL

---

### Task 4.5: Integration Testing (Days 11–13)

**Objective:** Test full application flow

**Steps:**

1. **Create E2E Tests**
   ```javascript
   // frontend/src/__tests__/integration.test.js
   import React from 'react';
   import { render, screen, waitFor } from '@testing-library/react';
   import userEvent from '@testing-library/user-event';
   import Dashboard from '../pages/Dashboard';
   
   describe('GeoMRV End-to-End', () => {
       test('Create project -> Upload boundary -> Run job -> View results', async () => {
           render(<Dashboard />);
           
           // Create project
           const createBtn = screen.getByText('New Project');
           await userEvent.click(createBtn);
           // ...fill form
           // ...verify project created
           
           // Upload boundary
           // ...
           
           // Run monitoring job
           // ...
           
           // View results
           // ...
       });
   });
   ```

**Deliverables:**
- [ ] E2E tests written
- [ ] Full workflow tested
- [ ] Dashboard operational
- [ ] All features functional

---

## ✅ Phase 4 Checklist

- [ ] React app created
- [ ] API client implemented
- [ ] Dashboard component
- [ ] Project form
- [ ] Boundary viewer
- [ ] Job status tracker
- [ ] Results panel
- [ ] Timelapse preview player
- [ ] Evidence download
- [ ] Project detail page
- [ ] Routing configured
- [ ] Azure Static Web Apps deployed
- [ ] Environment variables set
- [ ] E2E tests passing
- [ ] Frontend functional

---

## 📊 Phase 4 Deliverables

| Component | Status | Notes |
|-----------|--------|-------|
| React Dashboard | ✅ | Full project management |
| Project Operations | ✅ | Create, view, upload boundary |
| Job Monitoring | ✅ | Real-time status tracking |
| Results Visualization | ✅ | Charts and metrics |
| Evidence Management | ✅ | Generation and download |
| Azure Deployment | ✅ | Public URL accessible |

---

**Next Phase:** [Phase 5: Testing & Launch](phase5_testing_launch.md)  
**Timeline:** Weeks 14–16
