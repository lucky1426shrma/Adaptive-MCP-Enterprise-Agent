# 🚀 Production Deployment Guide: Adaptive MCP Enterprise Agent

This guide provides the complete blueprint for deploying the **Adaptive MCP Enterprise Agent** stack to production with **100% functionality, reliability, zero downtime, and production security**.

---

## 🏗️ Production Architecture Overview

In production, the microservices operate inside a secure Virtual Private Cloud (VPC):

```
                               ┌───────────────────────────┐
                               │   CDN / Reverse Proxy     │
                               │   (Cloudflare / NGINX)    │
                               └─────────────┬─────────────┘
                                             │ HTTPS (Port 443)
                                             ▼
                               ┌───────────────────────────┐
                               │   Next.js Frontend UI     │
                               │   (AWS ECS / Vercel)      │
                               └─────────────┬─────────────┘
                                             │ HTTPS
                                             ▼
                               ┌───────────────────────────┐
                               │    FastAPI Backend        │
                               │  (AWS ECS / Cloud Run)    │
                               └─────────────┬─────────────┘
                                             │
                 ┌───────────────────────────┼───────────────────────────┐
                 │ Private Subnet (VPC)      │ Private Subnet (VPC)      │ Private Subnet (VPC)
                 ▼                           ▼                           ▼
     ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
     │      db-mcp          │    │      rag-mcp         │    │     github-mcp       │
     │  (AWS ECS / Docker)  │    │  (AWS ECS / Docker)  │    │  (AWS ECS / Docker)  │
     └──────────┬───────────┘    └──────────┬───────────┘    └──────────┬───────────┘
                │                           │                           │
                ▼                           ▼                           ▼
     ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
     │   AWS RDS PostgreSQL │    │ Qdrant Cloud Cluster │    │   GitHub REST API    │
     │   (Managed DB)       │    │  (Managed Vector DB) │    │  (Production Token)  │
     └──────────────────────┘    └──────────────────────┘    └──────────────────────┘
```

---

## 📋 Step-by-Step Production Deployment Blueprint

### Step 1: Managed Backing Infrastructure Setup
Do not run PostgreSQL or Qdrant as ephemeral single-container instances in production. Use managed enterprise equivalents:

1. **Managed PostgreSQL:**
   - Provision an **AWS RDS PostgreSQL 16** or **GCP Cloud SQL** instance.
   - Enable Multi-AZ replication and automated daily snapshots.
2. **Managed Vector Database:**
   - Provision a **Qdrant Cloud Cluster** (or self-host Qdrant on EC2 with persistent EBS SSD storage).

---

### Step 2: Production LLM Provider Configuration
For zero rate-limiting and guaranteed SLAs in production:
* Upgrade your OpenRouter account to a **paid tier** or configure production models (e.g., `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`).
* Update `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` in your production Secrets Manager.

---

### Step 3: Container Registry Build & Push (CI/CD)

Build production Docker images for all 5 services and push them to **Amazon ECR** or **Google Artifact Registry**:

```bash
# 1. Authenticate with AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# 2. Build and tag images
docker build -t adaptive-backend ./backend
docker build -t adaptive-frontend ./frontend
docker build -t adaptive-rag-mcp ./services/rag-mcp
docker build -t adaptive-db-mcp ./services/db-mcp
docker build -t adaptive-github-mcp ./services/github-mcp

# 3. Push to ECR
docker tag adaptive-backend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/adaptive-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/adaptive-backend:latest
# (Repeat tag and push for remaining 4 services)
```

---

### Step 4: Network Isolation & VPC Security Rules

1. **Public Subnet:**
   - Expose ONLY the **Next.js Frontend** (Port 443) and **FastAPI Backend API** via an AWS Application Load Balancer (ALB) or NGINX reverse proxy with TLS certificates (AWS Certificate Manager / Let's Encrypt).
2. **Private VPC Subnet:**
   - Place `db-mcp`, `rag-mcp`, and `github-mcp` inside private VPC subnets.
   - Configure Security Groups so MCP ports (`8001`, `8002`, `8003`) accept traffic **only from the FastAPI Backend security group**.

---

### Step 5: Database Seeding & Knowledge Base Ingestion

Run the one-off setup jobs against your production RDS and Qdrant instances:

```bash
# 1. Apply schema and provision read-only DB role against AWS RDS
python -m db.setup_and_seed \
  --admin-database-url "postgresql://postgres:<RDS_PASSWORD>@<RDS_ENDPOINT>:5432/adaptive_mcp" \
  --reader-password "<PRODUCTION_READER_PASSWORD>"

# 2. Run initial document ingestion into Qdrant Cloud
python -m scripts.ingest \
  --docs-dir "data/sample_docs"
```

---

### Step 6: Environment Variables & Secrets Management

Store secrets securely in **AWS Secrets Manager** or **HashiCorp Vault**:

```env
# Production Environment Variables
ENVIRONMENT=production
OPENROUTER_API_KEY=sk-or-v1-prod-xxxxxxxxx
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
RAG_MCP_AUTH_TOKEN=prod-super-secret-rag-token
DB_MCP_AUTH_TOKEN=prod-super-secret-db-token
GITHUB_MCP_AUTH_TOKEN=prod-super-secret-github-token
DATABASE_URL=postgresql://db_mcp_reader:<PRODUCTION_READER_PASSWORD>@<RDS_ENDPOINT>:5432/adaptive_mcp
QDRANT_URL=https://<QDRANT_CLOUD_CLUSTER_URL>:6333
BACKEND_API_KEY=prod-backend-gate-key-xxxx
CORS_ALLOWED_ORIGINS=https://agent.yourdomain.com
```

---

## ⚡ Option B: Quick Single-VM Production Deployment (AWS EC2 / DigitalOcean)

If deploying to a single production Linux server (EC2 / VPS):

1. **SSH into your server & install Docker Compose:**
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2
   ```
2. **Clone the repository & create `infrastructure/.env`**:
   ```bash
   git clone https://github.com/lucky1426shrma/Adaptive-MCP-Enterprise-Agent.git
   cd Adaptive-MCP-Enterprise-Agent/infrastructure
   cp .env.example .env
   # Add your production API key and secrets to .env
   ```
3. **Set up Caddy / NGINX SSL Reverse Proxy (Auto-HTTPS)**:
   ```caddy
   # /etc/caddy/Caddyfile
   agent.yourdomain.com {
       reverse_proxy localhost:3000
   }
   ```
4. **Launch production containers**:
   ```bash
   docker compose up -d
   docker compose run --rm db-mcp-setup
   docker compose run --rm rag-mcp-ingest
   ```

---

## 🛡️ Production Readiness Checklist

- [x] **SSL/TLS Encryption:** All traffic routed over HTTPS (Port 443).
- [x] **PII Log Redaction:** Verified `log_redaction.py` is scrubbing keys/passwords in logs.
- [x] **Rate Limit Resilience:** Exponential backoff retries active in `openrouter_provider.py`.
- [x] **Least Privilege:** PostgreSQL role restricted to `SELECT` queries only.
- [x] **Health Checks:** Container health checks active on `/health/ready`.
- [x] **Distributed Tracing:** OpenTelemetry exporting spans to your OTLP collector (Jaeger/Datadog).
