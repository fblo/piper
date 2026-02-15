#!/bin/bash

# Script pour se reconnecter au cluster Kubernetes
# Utilisation: ./reconnect-cluster.sh [TOKEN]

echo "Reconnexion au cluster Kubernetes: api-k8s-int.hostics.fr:6443"

if [ -z "$1" ]; then
    echo "Veuillez fournir un token d'authentification:"
    read -s TOKEN
else
    TOKEN=$1
fi

# Mise à jour de la configuration kubectl avec le nouveau token
kubectl config set-credentials kubernetes-admin --token="$TOKEN"
kubectl config set-context kubernetes-admin@kubernetes --cluster=kubernetes --user=kubernetes-admin
kubectl config use-context kubernetes-admin@kubernetes

echo "Configuration mise à jour. Test de la connexion..."

# Test de la connexion
kubectl cluster-info

if [ $? -eq 0 ]; then
    echo "Connexion réussie !"
    echo ""
    echo "Vous pouvez maintenant déployer Piper avec:"
    echo "kubectl apply -f kubernetes/deployment.yaml"
    echo "kubectl apply -f kubernetes/service.yaml"
else
    echo "Échec de la connexion. Vérifiez que le token est valide."
fi
</write_to_file>