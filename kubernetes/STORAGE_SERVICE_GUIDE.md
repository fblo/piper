# Guide pour le Persistent Volume et ClusterIP spécifique

Les fichiers Kubernetes ont été mis à jour pour répondre aux nouvelles exigences :

## Modifications apportées

### 1. Persistent Volume Claim pour /opt/voices

**Fichier créé** : `piper-pvc.yaml`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: piper-voices-pvc
  namespace: piper
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: standard
```

**Avantages** :
- **Persistance** : Les données dans `/opt/voices` survivent aux redémarrages des pods
- **Capacité** : 5Gi de stockage dédié
- **Performance** : Utilise la classe de stockage par défaut (standard)

### 2. Déploiement mis à jour

**Fichier modifié** : `piper-deploy.yaml`

Le déploiement utilise maintenant le Persistent Volume Claim au lieu du volume éphémère :

```yaml
volumes:
- name: voices-volume
  persistentVolumeClaim:
    claimName: piper-voices-pvc
```

### 3. Service avec ClusterIP spécifique

**Fichier modifié** : `piper-service.yaml`

Le service utilise maintenant une ClusterIP statique :

```yaml
clusterIP: 10.199.10.19
type: LoadBalancer
```

## Comment appliquer ces modifications

### Si vous déployez pour la première fois dans le namespace "piper" :

```bash
# 1. Créer le namespace (par un admin)
kubectl create namespace piper

# 2. Créer le Persistent Volume Claim
kubectl apply -f piper-pvc.yaml

# 3. Déployer l'application
kubectl apply -f piper-deploy.yaml

# 4. Déployer le service
kubectl apply -f piper-service.yaml
```

### Si vous migrez depuis le déploiement existant :

```bash
# 1. Supprimer l'ancien déploiement
kubectl delete deployment piper-deployment
kubectl delete service piper-service

# 2. Suivre les étapes ci-dessus pour déployer dans le namespace "piper"
```

## Vérification

Une fois déployé :

```bash
# Vérifier le PVC
kubectl get pvc -n piper

# Vérifier le pod
kubectl get pods -n piper

# Vérifier le service avec la ClusterIP spécifique
kubectl get services -n piper

# Accéder à l'application
curl http://10.199.10.19:5051
```

## Configuration Calico

Comme vous utilisez Calico, voici quelques commandes utiles :

```bash
# Vérifier les politiques réseau
kubectl get networkpolicy -n piper

# Vérifier la connectivité entre pods
calicoctl node status
```

## Notes importantes

1. **StorageClass** : Le PVC utilise `storageClassName: standard`. Si votre cluster utilise une autre classe de stockage par défaut, vous devrez peut-être modifier cette valeur.

2. **ClusterIP** : L'adresse `10.199.10.19` doit être dans la plage des ClusterIPs configurée pour votre cluster Kubernetes.

3. **Permissions** : Assurez-vous que le namespace "piper" existe avant d'appliquer les fichiers, ou demandez à un administrateur de le créer pour vous.

4. **Migration des données** : Si vous aviez des données dans l'ancien volume `emptyDir`, elles seront perdues lors de la migration vers le Persistent Volume.