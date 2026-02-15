# Piper TTS Helm Chart

A Helm chart for deploying Piper TTS application on Kubernetes with persistent storage and ClusterIP service.

## Features

- **Namespace isolation** - Deploys in dedicated "piper" namespace
- **Persistent storage** - 5Gi PVC for voice files at `/opt/voices`
- **ClusterIP service** - Fixed IP `10.199.10.19` on port 5051
- **Resource limits** - Configurable CPU and memory
- **Calico compatible** - No Ingress required

## Prerequisites

- Kubernetes 1.19+
- Helm 3+
- StorageClass "standard" available (or modify values.yaml)
- ClusterIP range includes `10.199.10.19`

## Installation

### Add the chart (if using a repository)

```bash
helm repo add piper https://your-repo-url
helm repo update
```

### Install from local directory

```bash
# Install with default values
helm install piper ./piper-chart

# Install with custom values
helm install piper ./piper-chart -f custom-values.yaml
```

### Install in existing namespace

```bash
# If namespace already exists
helm install piper ./piper-chart --set namespace.create=false
```

## Configuration

Edit `values.yaml` or create a custom values file:

```yaml
namespace:
  name: piper
  create: true

piper:
  replicaCount: 1

  image:
    repository: vs-inf-prd-for-fr-501.hostics.fr/connectics/fblo/piper
    tag: latest
    pullPolicy: IfNotPresent

  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "1Gi"
      cpu: "1"

  service:
    type: ClusterIP
    port: 5051
    targetPort: 5051
    clusterIP: "10.199.10.19"

  persistence:
    enabled: true
    storageClass: "standard"
    accessMode: ReadWriteOnce
    size: 5Gi
    mountPath: /opt/voices
```

## Upgrading

```bash
helm upgrade piper ./piper-chart
```

## Uninstalling

```bash
helm uninstall piper
```

## Accessing the Service

```bash
# Get service details
kubectl get svc -n piper

# Access from within cluster
curl http://10.199.10.19:5051

# Port-forward for local testing
kubectl port-forward -n piper svc/piper-service 5051:5051
```

## Storage

The chart creates a PersistentVolumeClaim for voice files:

```bash
kubectl get pvc -n piper
```

## Troubleshooting

```bash
# Check pods
kubectl get pods -n piper

# View logs
kubectl logs -n piper -l app=piper

# Check events
kubectl get events -n piper
```

## Values Reference

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace.name` | Namespace name | `piper` |
| `namespace.create` | Create namespace | `true` |
| `piper.replicaCount` | Number of replicas | `1` |
| `piper.image.repository` | Image repository | `vs-inf-prd-for-fr-501.hostics.fr/connectics/fblo/piper` |
| `piper.image.tag` | Image tag | `latest` |
| `piper.image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `piper.service.type` | Service type | `ClusterIP` |
| `piper.service.port` | Service port | `5051` |
| `piper.service.clusterIP` | Fixed ClusterIP | `10.199.10.19` |
| `piper.persistence.enabled` | Enable persistence | `true` |
| `piper.persistence.size` | Storage size | `5Gi` |
| `piper.persistence.storageClass` | Storage class | `standard` |
| `piper.persistence.mountPath` | Mount path | `/opt/voices` |
</write_to_file>