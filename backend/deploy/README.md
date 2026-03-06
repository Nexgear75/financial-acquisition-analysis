# Deployment templates (production)

This folder contains copy-ready templates for production deployment with runtime secret injection.

## Structure

- `systemd/ma-mna-analyzer.service`: systemd unit running uvicorn.
- `systemd/secrets.env.example`: template for `/etc/ma-mna-analyzer/secrets.env`.
- `compose/docker-compose.prod.yml`: Docker Compose production service.
- `compose/.env.prod.example`: runtime env template used by compose.
- `k8s/deployment.yaml`: Kubernetes Deployment + Service.
- `k8s/secret.example.yaml`: Kubernetes Secret template.

## systemd quick start

1. Copy service file:
   - `sudo cp deploy/systemd/ma-mna-analyzer.service /etc/systemd/system/`
2. Create secrets file:
   - `sudo mkdir -p /etc/ma-mna-analyzer`
   - `sudo cp deploy/systemd/secrets.env.example /etc/ma-mna-analyzer/secrets.env`
   - Edit and set `OPENAI_API_KEY`, then `sudo chmod 600 /etc/ma-mna-analyzer/secrets.env`
3. Enable service:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now ma-mna-analyzer`

## Docker Compose quick start

1. Create runtime env file:
   - `cp deploy/compose/.env.prod.example deploy/compose/.env.prod`
   - Edit and set `OPENAI_API_KEY`
2. Start service:
   - `docker compose --env-file deploy/compose/.env.prod -f deploy/compose/docker-compose.prod.yml up -d`

## Kubernetes quick start

1. Create secret from template:
   - `cp deploy/k8s/secret.example.yaml deploy/k8s/secret.yaml`
   - Edit and set `OPENAI_API_KEY`
2. Apply manifests:
   - `kubectl apply -f deploy/k8s/secret.yaml`
   - `kubectl apply -f deploy/k8s/deployment.yaml`

## Security notes

- Never commit real secret files.
- Rotate `OPENAI_API_KEY` regularly.
- Restrict read access to secret files and cluster namespaces.
