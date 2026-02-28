# Azure Resource Setup (Phase 0)

Last updated: 2026-02-27
Environment: `dev`

## 1) Subscription + Resource Group

- **Subscription Name:** Azure for Students
- **Subscription ID:** `d9b38896-cff0-491b-a1ab-498a6edc9205`
- **Tenant/Directory ID:** `<fill-from-Microsoft-Entra-overview>`
- **Resource Group:** `geomrv-dev`
- **Region:** `Central India`

How to find:
- Azure Portal -> Subscriptions -> Azure for Students -> Overview
- Azure Portal -> Resource groups -> geomrv-dev -> Overview

---

## 2) Storage Account (Blob)

- **Storage Account Name:** `geomrvstoragedev`
- **Primary Blob Endpoint:** `<https://geomrvstoragedev.blob.core.windows.net/>`
- **Container 1:** `evidence-packages`
- **Container 2:** `satellite-data-cache`
- **Connection String:** `<from Access keys>`
- **Account Key (key1 or key2):** `<from Access keys>`

How to find:
- Azure Portal -> Storage accounts -> geomrvstoragedev -> Overview (endpoints)
- Azure Portal -> Storage accounts -> geomrvstoragedev -> Security + networking -> Access keys
- Azure Portal -> Storage accounts -> geomrvstoragedev -> Data storage -> Containers

Store in Key Vault secrets:
- `azure-storage-connection-string`
- `azure-storage-account-key`
- `azure-storage-account-name`

---

## 3) Key Vault

- **Key Vault Name:** `geomrv-kv`
- **Vault URI:** `<from Overview>`
- **Permission Model:** `Azure RBAC`
- **Your Role Assignment:** `Key Vault Administrator` (or Secrets Officer)

How to find:
- Azure Portal -> Key vaults -> geomrv-kv -> Overview
- Azure Portal -> Key vaults -> geomrv-kv -> Access control (IAM)

Recommended secrets to create now:
- `azure-storage-connection-string`
- `azure-storage-account-key`
- `azure-storage-account-name`
- `postgres-host`
- `postgres-db`
- `postgres-user`
- `postgres-password`
- `postgres-port`
- `appinsights-connection-string`
- `google-earth-engine-credentials`

---

## 4) Application Insights

- **Name:** `geomrv-insights`
- **Connection String:** `<from Overview>`
- **Instrumentation Key (legacy):** `<optional>`
- **Workspace:** `DefaultWorkspace-d9b38896-cff0-491b-a1ab-498a6edc9205-CID`

How to find:
- Azure Portal -> Application Insights -> geomrv-insights -> Overview

Store in Key Vault secret:
- `appinsights-connection-string`

---

## 5) PostgreSQL (fill after creation)

- **Server Name:** `geomrv-postgres-dev`
- **Host/FQDN:** `<server>.postgres.database.azure.com`
- **Port:** `5432`
- **Admin User:** `adminuser`
- **Database (dev):** `geomrv_dev`
- **Database (test):** `geomrv_test`
- **Database (prod):** `geomrv_prod`
- **SSL Required:** `true`

How to find:
- Azure Portal -> Azure Database for PostgreSQL -> geomrv-postgres-dev -> Overview
- Azure Portal -> Connection strings

Store in Key Vault secrets:
- `postgres-host`
- `postgres-port`
- `postgres-user`
- `postgres-password`
- `postgres-db`

---

## 6) Env var <-> Key Vault secret mapping

- `AZURE_STORAGE_ACCOUNT` <-> `azure-storage-account-name`
- `AZURE_STORAGE_ACCOUNT_KEY` <-> `azure-storage-account-key`
- `AZURE_STORAGE_CONNECTION_STRING` <-> `azure-storage-connection-string`
- `APPINSIGHTS_CONNECTION_STRING` <-> `appinsights-connection-string`
- `POSTGRES_HOST` <-> `postgres-host`
- `POSTGRES_PORT` <-> `postgres-port`
- `POSTGRES_DB` <-> `postgres-db`
- `POSTGRES_USER` <-> `postgres-user`
- `POSTGRES_PASSWORD` <-> `postgres-password`
- `GOOGLE_EARTH_ENGINE_CREDENTIALS` <-> `google-earth-engine-credentials`

---

## 7) What goes where (important)

- **Key Vault:** real secret values only.
- **.env.example in repo:** placeholders only, never real keys/passwords.
- **.env local file:** real values for your machine only, never commit.

---

## 8) Quick copy checklist

- [ ] Storage connection string copied
- [ ] Storage key copied
- [ ] App Insights connection string copied
- [ ] PostgreSQL host/user/password copied
- [ ] All above stored as Key Vault secrets
- [ ] `.env.example` updated with placeholders
- [ ] `.env` created locally from `.env.example`
