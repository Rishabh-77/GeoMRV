# Azure Cost Estimation & Student Pack Strategy

**Document Purpose:** Detailed budget planning for MVP using Azure Student Pack  
**Last Updated:** Feb 27, 2026

---

## 📊 Azure Student Pack Benefits

| Benefit | Value | Duration |
|---------|-------|----------|
| Azure Credits | $100/month | 12 months |
| Virtual Machines | 750 hours/month | Lifetime |
| App Service | 10 free web apps | Lifetime |
| SQL Database | 1 DB free tier | Lifetime |
| Storage | 5 GB free | Lifetime |
| Cognitive Services | Free tier access | Lifetime |

---

## 💰 MVP Monthly Cost Breakdown (Single Project Operation)

### COMPUTE SERVICES

**Azure App Service (Backend API)**
- Plan: B1 (1 CPU, 1.75 GB RAM)
- Cost: $10.50/month
- Alternative: F1 free tier (512MB) - consider for Phase 1 testing
- Usage: Running API server 24/7
- Estimate: **$10.50**

**Azure Functions (Optional Background Jobs)**
- If used for async processing
- Free tier: 1 million executions/month
- Estimate: **$0** (within free tier)

### DATABASE SERVICES

**Azure Database for PostgreSQL**
- Single Server: 1 vCore, 20 GB storage
- Base cost: $15/month
- Storage: $0.12/GB excess (included in plan)
- Backups: Included
- Estimate: **$15/month**

### STORAGE SERVICES

**Azure Blob Storage**
- Hot tier storage: $0.024/GB/month
- Expected usage: 5 GB (100 projects × 50MB each)
- Cost: 5 × $0.024 = $0.12/month

- Data ingress (from Earth Engine): Free
- Data egress (downloads): $0.12/GB
- Expected: 10 GB/month (10 evidence packages)
- Cost: 10 × $0.12 = $1.20/month

- Total storage estimate: **$1.32/month**

### MONITORING & LOGGING

**Application Insights**
- Ingestion: First 1 GB free/month
- Expected ingestion: 500 MB/month
- Estimate: **$0** (within free tier)

**Log Analytics**
- 5 GB/month included free
- Expected logs: 2-3 GB/month
- Estimate: **$0** (within free tier)

### INTEGRATION SERVICES

**Key Vault**
- Operations: $0.03 per 10,000
- Certificates: $0.66/month
- Expected: 20-30 operations/day
- Estimate: **$0.66/month**

### NETWORKING

**Static IP Address**
- If using dedicated IP: $4/month
- With load balancer: $18/month
- For MVP: Not needed (App Service default)
- Estimate: **$0** (included in App Service)

**Data Transfer**
- Intra-region transfer: Free
- All Azure services in same region
- Estimate: **$0**

---

## 📈 TOTAL MONTHLY COST SUMMARY

| Service | Cost |
|---------|------|
| App Service | $10.50 |
| PostgreSQL | $15.00 |
| Blob Storage | $1.32 |
| Key Vault | $0.66 |
| Monitoring | $0.00 |
| **SUBTOTAL** | **$27.48** |

**Student Pack Credit Used:** $27.48 of $100  
**Remaining Monthly Credit:** $72.52  
**Buffer for Overages:** Excellent

---

## 🔄 Cost Per Monitoring Cycle (per project)

**Scenario: Running 1 monitoring job (1 year of satellite data)**

| Activity | Resource | Cost |
|----------|----------|------|
| Satellite data fetch | Earth Engine | $0 (academic free) |
| Feature extraction | CPU compute | $0.50 |
| ML inference | App Service | $0.30 |
| Report generation | CPU + PDF libs | $0.20 |
| Evidence storage | Blob Storage | $0.50 |
| Database queries | PostgreSQL | $0.25 |
| **Total per cycle** | | **~$1.75** |

**Cost per project per year** (4 monitoring cycles): ~$7

---

## 📊 COST SCALING SCENARIOS

### Scenario 1: 10 Projects (5 monitoring cycles each/year)

| Service | Current | Scaled | Notes |
|---------|---------|--------|-------|
| App Service | $10.50 | $21 | Upgrade to B2 for load |
| PostgreSQL | $15 | $30 | vCore 2, 100GB storage |
| Storage | $1.32 | $15 | 500 projects × 100MB |
| **Monthly** | $27.48 | $66 | Still under $100 credit |

### Scenario 2: 50+ Projects (Production)

| Service | Cost |
|---------|------|
| App Service | $50 (B3 with auto-scale) |
| PostgreSQL | $60 (vCore 4) |
| Storage | $50 (5 TB) |
| Monitoring | $10 |
| **Monthly** | **$170** |

**Note:** Exceeds Student Pack, requires paid subscription. Recommend graduated pricing model for projects.

---

## 💡 Cost Optimization Strategies

### 1. **Use Free Tiers Aggressively**
- ✅ App Service F1 tier during dev (512MB)
- ✅ PostgreSQL single vCore (minimal at start)
- ✅ First 5GB blob storage free
- ✅ Log Analytics 5GB free tier
- ✅ Application Insights 1GB free

### 2. **Reserved Capacity (When Scaling)**
- SQL Database: 1-year reservations save 40%
- App Service: Committed plans for consistent load

### 3. **Data Management**
- Archive old evidence packages to cool/archive tier
- Delete test data regularly
- Compress satellite data cache
- Expected saving: $2-5/month at scale

### 4. **Scheduled Operations**
- Run batch jobs during off-peak (cheaper compute)
- Satellite data fetches at night
- Model retraining monthly (not daily)

### 5. **Geographic Optimization**
- Use Southeast Asia region (lower costs than US)
- Keep all services in same region (free intra-region transfer)
- CDN caching for static assets (minimal for MVP)

---

## 🎯 Student Pack Financial Strategy

### Phase 1-2 (Months 1-3): Development
- Use F1 app service free tier
- PostgreSQL basic (1 vCore)
- Expected cost: **$15-18/month**
- Credits consumed: ~$50 total

### Phase 3-4 (Months 4-6): Testing & Validation
- Upgrade to B1 for performance testing
- Add Application Insights for monitoring
- Expected cost: **$25-30/month**
- Credits consumed: ~$80 total

### Phase 5-6 (Months 7-12): Production MVP
- B1 App Service (stable)
- PostgreSQL 1 vCore (sufficient)
- Full monitoring stack
- Expected cost: **$27-35/month**
- Credits consumed: $324 (full year)

### Month 13+: Post Student Pack

**Three Options:**

1. **Continue on Azure Pay-as-You-Go**
   - Monthly cost: $30-50
   - Charge clients: $100-200/project/year
   - Gross margin: 60-80%

2. **Hybrid: On-Premises + AWS**
   - Move compute to cheaper cloud provider
   - Keep data in Azure for partner integrations
   - Cost: $20-30/month

3. **Containerization + Kubernetes**
   - Deploy on Azure Container Instances
   - Auto-scaling based on demand
   - Cost: Pay-per-second model
   - Better for variable load

**Recommendation:** Option 1 (Continue Azure) - Simplifies architecture, avoids multi-cloud complexity.

---

## 📈 Revenue Model & Unit Economics

### Service Pricing (Recommended)

**Per Project Annual Fee:**
- Starter: $500/year (1 monitoring cycle)
- Professional: $1,500/year (quarterly monitoring)
- Enterprise: $5,000/year (monthly monitoring + support)

**Per-Use Pricing (Alternative):**
- Evidence package generation: $50/cycle
- Custom verification rules: $500 setup
- Technical support: $100/hour

### Unit Economics Example

**Professional Tier: $1,500/year = $125/month**

| Cost | Amount |
|------|--------|
| Azure infrastructure | $30 |
| Satellite data | $2 |
| Personnel (support) | $50 |
| **Gross Profit** | **$43/month** |
| **Gross Margin** | **34%** |

**To reach 60% margin:**
- Increase price to $250/month per project
- Reduce support time through automation

---

## 🔐 Cost Control Guardrails

### Monthly Cost Limits
- Set Azure budget alert at $75/month
- Set alert at $90/month for immediate review
- Hard limit: $100 (Student Pack max)

### Resource Quotas
- App Service: B2 maximum
- Database: 2 vCore maximum
- Storage: 100 GB maximum

### Monitoring Dashboard
```python
# Create Azure monitor dashboard for costs
from azure.mgmt.costmanagement import CostManagementClient

def get_daily_costs():
    client = CostManagementClient(credential)
    # Query costs for last 7 days
    # Alert if trending over budget
```

---

## 📋 Cost Verification Checklist

- [ ] Azure billing verified for actual vs. estimate
- [ ] No unexpected charges identified
- [ ] Reserved instances considered for scaling
- [ ] Student Pack renewal confirmed for next year
- [ ] Cost allocation by service documented
- [ ] Budget alerts configured
- [ ] Growth trajectory modeled for profitability

---

## References

- [Azure Student Pack](https://azure.microsoft.com/en-us/free/students)
- [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator)
- [Azure Cost Management](https://azure.microsoft.com/en-us/services/cost-management)
- [India Azure Regions](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-available-by-region/)
