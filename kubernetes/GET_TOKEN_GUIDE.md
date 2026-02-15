# Guide pour récupérer un token Kubernetes

Voici plusieurs méthodes pour obtenir un token d'authentification pour votre cluster Kubernetes :

## Méthode 1: Utiliser un Service Account existant

Si vous avez accès à un Service Account avec les permissions appropriées :

```bash
# Lister les service accounts disponibles
kubectl get serviceaccounts

# Créer un token pour un service account spécifique
kubectl create token <nom-du-service-account>
```

## Méthode 2: Vérifier les secrets existants

Les tokens sont souvent stockés dans des secrets Kubernetes :

```bash
# Lister tous les secrets
kubectl get secrets

# Afficher les détails d'un secret spécifique
kubectl describe secret <nom-du-secret>

# Extraire le token d'un secret
kubectl get secret <nom-du-secret> -o jsonpath='{.data.token}' | base64 --decode
```

## Méthode 3: Créer un nouveau Service Account et token

Si vous avez les permissions pour créer des Service Accounts :

```bash
# Créer un nouveau Service Account
kubectl create serviceaccount piper-deployer

# Créer un ClusterRoleBinding pour donner les permissions
kubectl create clusterrolebinding piper-deployer-binding \
  --clusterrole=edit \
  --serviceaccount=default:piper-deployer

# Générer un token pour ce Service Account
kubectl create token piper-deployer
```

## Méthode 4: Utiliser l'interface web du cluster

Si votre cluster a une interface web (comme Rancher, OpenShift, ou le dashboard Kubernetes) :

1. Connectez-vous à l'interface web de votre cluster
2. Naviguez vers la section "Service Accounts" ou "Utilisateurs"
3. Trouvez votre compte ou créez-en un nouveau
4. Générez ou affichez le token d'authentification

## Méthode 5: Demander à l'administrateur du cluster

Si vous n'avez pas les permissions pour créer des tokens :

1. Contactez l'administrateur de votre cluster Kubernetes
2. Demandez-lui de vous fournir un token avec les permissions nécessaires
3. Précisez que vous avez besoin des permissions pour déployer des applications dans un namespace

## Méthode 6: Vérifier votre configuration actuelle

Votre configuration kubectl actuelle contient peut-être déjà un token :

```bash
# Afficher la configuration complète
kubectl config view --raw

# Extraire le token actuel (si présent)
kubectl config view --raw -o jsonpath='{.users[?(@.name=="kubernetes-admin")].user.token}'
```

## Utilisation du token

Une fois que vous avez obtenu un token, utilisez-le avec le script de reconnexion :

```bash
./reconnect-cluster.sh "votre-token-ici"
```

ou

```bash
./reconnect-cluster.sh
# Puis collez le token quand on vous le demande
```

## Sécurité importante

- Ne partagez jamais votre token avec des personnes non autorisées
- Les tokens ont une durée de vie limitée (généralement 1 an)
- Stockez les tokens dans des endroits sécurisés
- Supprimez les tokens inutilisés

Si vous avez besoin d'aide supplémentaire pour récupérer votre token, précisez quelle méthode vous souhaitez essayer ou décrivez votre environnement Kubernetes (Rancher, OpenShift, EKS, AKS, GKE, etc.) pour des instructions plus spécifiques.
<task_progress>
- [x] Lire le fichier Containerfile pour comprendre l'image Docker
- [x] Vérifier si une image Docker a déjà été construite
- [x] Créer les fichiers Kubernetes (Deployment et Service)
- [x] Appliquer les fichiers Kubernetes sur le cluster
- [x] Fournir un guide pour récupérer le token Kubernetes
</task_progress>
</write_to_file>