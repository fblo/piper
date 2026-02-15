# Déploiement de Piper sur Kubernetes

Ce dossier contient les fichiers nécessaires pour déployer l'application Piper sur un cluster Kubernetes.

## Fichiers créés

- `deployment.yaml` : Définition du déploiement Kubernetes pour Piper
- `service.yaml` : Définition du service Kubernetes pour exposer Piper
- `reconnect-cluster.sh` : Script pour se reconnecter au cluster Kubernetes

## Prérequis

1. Une image Docker de Piper déjà construite (disponible localement sous `localhost/piper:latest`)
2. Accès à un cluster Kubernetes
3. `kubectl` configuré pour accéder au cluster

## Procédure de déploiement

### 1. Se reconnecter au cluster Kubernetes

Votre configuration kubectl existe déjà mais les informations d'identification ont expiré. Utilisez le script fourni pour vous reconnecter :

```bash
./reconnect-cluster.sh
```

Le script vous demandera un nouveau token d'authentification.

### 2. Vérifier la connexion

Après avoir exécuté le script, vérifiez que vous êtes bien connecté :

```bash
kubectl cluster-info
```

### 3. Déployer l'application

Une fois connecté, déployez Piper avec les commandes suivantes :

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

### 4. Vérifier le déploiement

Vérifiez que les pods sont en cours d'exécution :

```bash
kubectl get pods
```

### 5. Accéder à l'application

Le service est configuré comme LoadBalancer. Pour accéder à Piper :

```bash
kubectl get services
```

Notez l'adresse IP externe du service `piper-service` et accédez-y sur le port 5051.

## Configuration du déploiement

- **Image utilisée** : `localhost/piper:latest`
- **Port exposé** : 5051
- **Ressources allouées** :
  - CPU : 500m (requis) / 1 (limite)
  - Mémoire : 512Mi (requis) / 1Gi (limite)
- **Volume** : Un volume `emptyDir` est monté sur `/opt/voices` pour les fichiers de voix

## Dépannage

Si vous rencontrez des problèmes :

1. Vérifiez que l'image Docker est disponible localement : `podman images`
2. Vérifiez les logs des pods : `kubectl logs <nom-du-pod>`
3. Vérifiez les événements Kubernetes : `kubectl get events`

## Alternative : Cluster local

Si vous préférez utiliser un cluster Kubernetes local pour les tests, vous pouvez installer :

- **Minikube** : `minikube start`
- **Kind** : `kind create cluster`

Puis déployez avec les mêmes commandes `kubectl apply`.
<task_progress>
- [x] Lire le fichier Containerfile pour comprendre l'image Docker
- [x] Vérifier si une image Docker a déjà été construite
- [x] Créer les fichiers Kubernetes (Deployment et Service)
- [x] Appliquer les fichiers Kubernetes sur le cluster
</task_progress>
</write_to_file>