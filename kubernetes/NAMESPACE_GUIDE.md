# Guide pour utiliser le namespace "piper"

Les fichiers Kubernetes ont été mis à jour pour utiliser un namespace dédié "piper". Voici comment procéder :

## Fichiers mis à jour

- `piper-deploy.yaml` - Déploiement avec namespace: piper
- `piper-service.yaml` - Service avec namespace: piper
- `piper-namespace.yaml` - Définition du namespace

## Étapes pour déployer dans le namespace "piper"

### Option 1: Si vous avez les permissions pour créer des namespaces

```bash
# Créer le namespace
kubectl apply -f piper-namespace.yaml

# Déployer les ressources dans le namespace
kubectl apply -f piper-deploy.yaml
kubectl apply -f piper-service.yaml
```

### Option 2: Si vous n'avez pas les permissions (recommandé)

Demandez à votre administrateur Kubernetes de :

1. Créer le namespace pour vous :
   ```bash
   kubectl create namespace piper
   ```

2. Vous donner les permissions sur ce namespace :
   ```bash
   kubectl create rolebinding piper-admin --clusterrole=admin --serviceaccount=piper:default --namespace=piper
   ```

3. Puis déployez vos ressources :
   ```bash
   kubectl apply -f piper-deploy.yaml
   kubectl apply -f piper-service.yaml
   ```

### Option 3: Déployer dans le namespace existant

Si le namespace "piper" existe déjà, vous pouvez simplement appliquer les fichiers :

```bash
kubectl apply -f piper-deploy.yaml
kubectl apply -f piper-service.yaml
```

## Vérification

Une fois déployé dans le namespace "piper" :

```bash
# Voir les pods dans le namespace piper
kubectl get pods -n piper

# Voir les services dans le namespace piper
kubectl get services -n piper

# Voir les logs
kubectl logs -n piper <nom-du-pod>
```

## Avantages du namespace

- **Isolation** : Séparation claire de vos ressources
- **Sécurité** : Permissions granulaires par namespace
- **Organisation** : Meilleure gestion des ressources
- **Quotas** : Possibilité de définir des quotas de ressources

## Migration depuis le déploiement actuel

Si vous souhaitez migrer votre déploiement actuel vers le namespace "piper" :

1. Supprimez l'ancien déploiement :
   ```bash
   kubectl delete deployment piper-deployment
   kubectl delete service piper-service
   ```

2. Suivez les étapes ci-dessus pour déployer dans le namespace "piper"