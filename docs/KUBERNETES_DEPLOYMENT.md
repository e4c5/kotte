# Kubernetes Deployment Plan for Kotte

This document describes how to deploy Kotte to Kubernetes with CloudNativePG, PostgreSQL-backed sessions and credentials, and high availability. Use this as the implementation guide when building the deployment.

---

## Overview

**Components:**
- **CloudNativePG Cluster** (2 instances) – PostgreSQL + Apache AGE
- **Backend** (2+ replicas) – FastAPI, sessions and credentials in PostgreSQL
- **Frontend** (2+ replicas) – Static assets via nginx

**No Redis** – Sessions and saved credentials use PostgreSQL.

---

## Prerequisites

- Kubernetes cluster (1.24+)
- `kubectl` and `helm` configured
- Container registry for custom AGE image
- StorageClass for dynamic provisioning (or cluster default)

---

## Implementation Checklist

### Phase 1: CloudNativePG + AGE

- [ ] **1.1** Install CloudNativePG operator
  ```bash
  helm repo add cnpg https://cloudnative-pg.github.io/charts
  helm repo update
  helm install cnpg cnpg/cloudnative-pg -n cnpg-system --create-namespace
  ```

- [ ] **1.2** Create custom PostgreSQL + AGE image
  - File: `deployment/Dockerfile.age-cnpg`
  - Base: `ghcr.io/cloudnative-pg/postgresql:16` (or compile AGE into CNPG base)
  - Must include Apache AGE extension
  - Reference: https://medium.com/percolation-labs/cloudnativepg-age-and-pg-vector-on-a-docker-image-step-1-ef0156c78f49

- [ ] **1.3** Build and push image
  ```bash
  docker build -f deployment/Dockerfile.age-cnpg -t <registry>/kotte-age-cnpg:latest .
  docker push <registry>/kotte-age-cnpg:latest
  ```

- [ ] **1.4** Extend init SQL
  - File: `deployment/init-db.sql` (or separate ConfigMap)
  - Add:
    - `CREATE EXTENSION IF NOT EXISTS age;` (already present)
    - `kotte_sessions` table for backend sessions
    - `kotte_credentials` table/schema for credential storage (if implementing postgresql backend)
  - Session table schema (example):
    ```sql
    CREATE TABLE IF NOT EXISTS kotte_sessions (
      session_id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      data JSONB NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      expires_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_kotte_sessions_expires ON kotte_sessions(expires_at);
    ```

- [ ] **1.5** Create CloudNativePG Cluster manifest
  - File: `deployment/k8s/age-cluster.yaml`
  - `spec.image`: `<registry>/kotte-age-cnpg:latest`
  - `spec.instances`: 2
  - `spec.storage.size`: e.g. 10Gi
  - `spec.bootstrap.initDB`: credentials, `postInitSQL` or initConfigMap for AGE + tables

---

### Phase 2: Backend – PostgreSQL-backed Sessions and Credentials

- [ ] **2.1** Implement PostgresSessionStore
  - File: `backend/app/core/session_store.py` (new) or extend `backend/app/core/auth.py`
  - Interface: `get(session_id)`, `set(session_id, data, ttl)`, `delete(session_id)`
  - Use `DB_*` settings for connection; run `LOAD 'age'` and set search_path if needed, or use separate connection for session store
  - Table: `kotte_sessions`

- [ ] **2.2** Wire SessionManager to PostgresSessionStore
  - File: `backend/app/core/auth.py`
  - Add config: `SESSION_STORAGE_TYPE` (values: `memory`, `postgresql`)
  - When `postgresql`, use PostgresSessionStore; else use existing in-memory store

- [ ] **2.3** Implement PostgreSQL credential storage (optional – or keep json_file on PVC)
  - Config already has `credential_storage_type: postgresql`
  - If not implemented: add `PostgresConnectionStorage` in `backend/app/core/connection_storage.py`
  - Schema: table for encrypted connection blobs (user_id, connection_id, encrypted_username, encrypted_password, name, host, port, database, sslmode, created_at)
  - Or: keep `json_file` and use a small PVC for `/app/data` – simpler but less HA-friendly

- [ ] **2.4** Add config support
  - File: `backend/app/core/config.py`
  - Add `session_storage_type: str = "memory"`
  - Ensure `CREDENTIAL_STORAGE_TYPE=postgresql` is supported if implementing

---

### Phase 3: Kubernetes Manifests

- [ ] **3.1** Namespace
  - File: `deployment/k8s/namespace.yaml`
  - e.g. `kotte` namespace

- [ ] **3.2** Secrets (template)
  - File: `deployment/k8s/secrets.yaml`
  - Keys: `SESSION_SECRET_KEY`, `MASTER_ENCRYPTION_KEY`, `DB_PASSWORD` (or use existing CNPG bootstrap)
  - Use placeholder values; document that prod should use Sealed Secrets / External Secrets

- [ ] **3.3** Backend ConfigMap
  - File: `deployment/k8s/configmap-backend.yaml`
  - `DB_HOST`: `kotte-age-rw` (CloudNativePG read-write service)
  - `DB_PORT`: `5432`
  - `CORS_ORIGINS`: frontend URL(s)
  - `ENVIRONMENT`: `production`
  - `CREDENTIAL_STORAGE_TYPE`: `postgresql` (or `json_file` if not implementing)
  - `SESSION_STORAGE_TYPE`: `postgresql`

- [ ] **3.4** Backend Deployment
  - File: `deployment/k8s/backend-deployment.yaml`
  - Image: backend image (build from `deployment/backend.Dockerfile`)
  - Replicas: 2
  - EnvFrom: ConfigMap + Secret
  - Liveness/readiness probes: `/api/v1/health`
  - No PVC if using PostgreSQL for sessions + credentials

- [ ] **3.5** Backend Service
  - File: `deployment/k8s/backend-service.yaml`
  - ClusterIP, port 8000

---

### Phase 4: Frontend

- [ ] **4.1** Production frontend Dockerfile
  - File: `deployment/frontend.Dockerfile.prod` or update `deployment/frontend.Dockerfile`
  - Stage 1: `node:20-alpine`, `npm ci`, `npm run build`
  - Stage 2: `nginx:alpine`, copy `dist/` from stage 1
  - nginx config: serve static, SPA fallback `try_files $uri /index.html`
  - Build arg: `VITE_API_BASE_URL` (e.g. `/api` for same-origin or full URL)

- [ ] **4.2** Frontend Deployment
  - File: `deployment/k8s/frontend-deployment.yaml`
  - Image: frontend production image
  - Replicas: 2

- [ ] **4.3** Frontend Service
  - File: `deployment/k8s/frontend-service.yaml`
  - ClusterIP, port 80

---

### Phase 5: Ingress (Optional)

- [ ] **5.1** Ingress
  - File: `deployment/k8s/ingress.yaml`
  - Single host, path-based: `/` → frontend, `/api` → backend
  - Or leave to cluster admins

---

### Phase 6: Production Hardening (Optional)

- [ ] Resource requests/limits for all deployments
- [ ] PodDisruptionBudgets
- [ ] CloudNativePG ScheduledBackup to object storage
- [ ] NetworkPolicies
- [ ] HorizontalPodAutoscaler

---

## File Layout

```
deployment/
├── Dockerfile.age-cnpg
├── init-db.sql                    # Extend with kotte_sessions, etc.
├── backend.Dockerfile             # Existing
├── frontend.Dockerfile.prod       # New production build
├── k8s/
│   ├── namespace.yaml
│   ├── secrets.yaml
│   ├── configmap-backend.yaml
│   ├── age-cluster.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml         # Optional
```

---

## Networking

| Service        | Port | Purpose                          |
|----------------|------|----------------------------------|
| kotte-age-rw   | 5432 | PostgreSQL primary (read-write)  |
| kotte-age-ro   | 5432 | PostgreSQL replicas (read-only)  |
| backend        | 8000 | FastAPI                          |
| frontend       | 80   | nginx static                     |

---

## Deployment Order

1. Install CloudNativePG operator
2. Apply `deployment/k8s/namespace.yaml`
3. Build and push AGE image; apply `age-cluster.yaml`
4. Wait for Cluster to be ready
5. Build and push backend image; apply secrets, configmap, backend deployment + service
6. Build and push frontend image; apply frontend deployment + service
7. Apply Ingress (if used)

---

## Environment Variables Reference

**Backend (K8s):**
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `SESSION_SECRET_KEY`, `MASTER_ENCRYPTION_KEY`
- `SESSION_STORAGE_TYPE=postgresql`
- `CREDENTIAL_STORAGE_TYPE=postgresql` (or `json_file`)
- `CORS_ORIGINS`, `ENVIRONMENT=production`

**Frontend (build-time):**
- `VITE_API_BASE_URL` – e.g. `/api` if same-origin via Ingress, or `https://api.example.com`

---

## Open Decisions

1. **Credential storage**: Implement `postgresql` backend or keep `json_file` with PVC?
2. **Image registry**: Where to push images (GHCR, Docker Hub, private)?
3. **Secrets**: Plain Secrets for dev or Sealed/External Secrets from start?
4. **Ingress**: Include basic Ingress or leave to cluster admins?
