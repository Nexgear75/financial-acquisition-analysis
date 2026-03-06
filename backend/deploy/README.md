# Templates de deploiement (production)

Ce dossier contient des templates prets a copier pour le deploiement production avec injection de secrets au runtime.

## Structure

- `systemd/ma-mna-analyzer.service` : unite systemd qui lance uvicorn.
- `systemd/secrets.env.example` : modele pour `/etc/ma-mna-analyzer/secrets.env`.
- `compose/docker-compose.prod.yml` : service Docker Compose pour la production.
- `compose/.env.prod.example` : modele de variables runtime pour Compose.
- `k8s/deployment.yaml` : Deployment + Service Kubernetes.
- `k8s/secret.example.yaml` : modele de Secret Kubernetes.

## Demarrage rapide systemd

1. Copier le fichier de service :
   - `sudo cp deploy/systemd/ma-mna-analyzer.service /etc/systemd/system/`
2. Creer le fichier de secrets :
   - `sudo mkdir -p /etc/ma-mna-analyzer`
   - `sudo cp deploy/systemd/secrets.env.example /etc/ma-mna-analyzer/secrets.env`
   - Renseigner `OPENAI_API_KEY`, puis `sudo chmod 600 /etc/ma-mna-analyzer/secrets.env`
3. Activer le service :
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now ma-mna-analyzer`

## Demarrage rapide Docker Compose

1. Creer le fichier d'environnement runtime :
   - `cp deploy/compose/.env.prod.example deploy/compose/.env.prod`
   - Renseigner `OPENAI_API_KEY`
2. Lancer le service (profil image distante) :
   - `docker compose --profile remote-image --env-file deploy/compose/.env.prod -f deploy/compose/docker-compose.prod.yml up -d`
3. Lancer le service (profil build local) :
   - `docker compose --profile local-build --env-file deploy/compose/.env.prod -f deploy/compose/docker-compose.prod.yml up -d backend-local --build`
4. Lancer le service (profil dev avec hot reload) :
   - `docker compose --profile dev --env-file deploy/compose/.env.prod -f deploy/compose/docker-compose.prod.yml up -d backend-dev --build`

## Demarrage rapide Kubernetes

1. Creer le secret a partir du modele :
   - `cp deploy/k8s/secret.example.yaml deploy/k8s/secret.yaml`
   - Renseigner `OPENAI_API_KEY`
2. Appliquer les manifests :
   - `kubectl apply -f deploy/k8s/secret.yaml`
   - `kubectl apply -f deploy/k8s/deployment.yaml`

## Notes de securite

- Ne jamais commit de fichiers secrets reels.
- Faire une rotation reguliere de `OPENAI_API_KEY`.
- Restreindre l'acces en lecture aux fichiers de secrets et aux namespaces Kubernetes.
