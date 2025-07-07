# Forge Deployment Guide

This guide provides step-by-step instructions for deploying the Forge application on AWS using either EC2 or EKS.

## Prerequisites

Before starting, ensure you have:
- AWS Account with appropriate permissions
- AWS CLI configured (`aws configure`)
- Docker installed
- kubectl (for EKS deployment)
- Access to the Forge Docker image

## 1. RDS Setup

First, set up the PostgreSQL database in RDS:

```bash
# Create RDS PostgreSQL Instance
aws rds create-db-instance \
    --db-instance-identifier forge-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username forge \
    --master-user-password <secure-password> \
    --allocated-storage 20 \
    --db-name forge \
    --vpc-security-group-ids <your-security-group-id> \
    --publicly-accessible false

# Wait for the instance to be available
aws rds wait db-instance-available --db-instance-identifier forge-db

# Get the RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier forge-db \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)
```

## 2. EC2 Deployment

### 2.1 Launch EC2 Instance

```bash
# Create security group
aws ec2 create-security-group \
    --group-name forge-sg \
    --description "Security group for Forge application"

# Add inbound rules
aws ec2 authorize-security-group-ingress \
    --group-name forge-sg \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-name forge-sg \
    --protocol tcp \
    --port 8000 \
    --cidr 0.0.0.0/0

# Launch EC2 instance
aws ec2 run-instances \
    --image-id ami-0c55b159cbfafe1f0 \
    --count 1 \
    --instance-type t2.micro \
    --key-name <your-key-pair> \
    --security-group-ids <forge-sg-id> \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=forge-app}]'
```

### 2.2 Configure EC2 Instance

```bash
# SSH into the instance
ssh -i <your-key-pair>.pem ec2-user@<ec2-public-ip>

# Install Docker
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create environment file
cat > .env << EOL
DATABASE_URL=postgresql://forge:<password>@${RDS_ENDPOINT}:5432/forge
PORT=8000
EOL

# Pull and run the application
docker pull tensorblockai/forge:latest
docker-compose -f docker-compose.prod.yml up -d
```

## 3. EKS Deployment

### 3.1 Create EKS Cluster

```bash
# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Create EKS cluster
eksctl create cluster \
    --name forge-cluster \
    --region <region> \
    --node-type t2.micro \
    --nodes 2 \
    --node-ami auto

# Update kubeconfig
aws eks update-kubeconfig --name forge-cluster --region <region>
```

### 3.2 Deploy Application

```bash
# Create namespace
kubectl create namespace forge

# Create secret for database credentials
kubectl create secret generic forge-secrets \
    --namespace forge \
    --from-literal=DATABASE_URL=postgresql://forge:<password>@${RDS_ENDPOINT}:5432/forge

# Deploy application
kubectl apply -f k8s/deployment.yaml -n forge
kubectl apply -f k8s/service.yaml -n forge

# Verify deployment
kubectl get pods -n forge
kubectl get svc -n forge
```

## 4. Verification

### 4.1 EC2 Verification

```bash
# Check if the container is running
docker ps

# Check application logs
docker logs forge-app

# Test the application
curl http://localhost:8000/health
```

### 4.2 EKS Verification

```bash
# Get the load balancer URL
kubectl get svc forge-service -n forge -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'

# Test the application
curl http://<load-balancer-url>/health
```

## 5. Maintenance

### 5.1 Updating the Application

#### EC2:
```bash
# Pull latest image
docker pull tensorblockai/forge:latest

# Restart the container
docker-compose -f docker-compose.prod.yml restart
```

#### EKS:
```bash
# Update the deployment
kubectl set image deployment/forge-app forge=tensorblockai/forge:latest -n forge

# Monitor the rollout
kubectl rollout status deployment/forge-app -n forge
```

### 5.2 Scaling

#### EC2:
```bash
# Scale up the instance type
aws ec2 modify-instance-attribute \
    --instance-id <instance-id> \
    --instance-type t2.medium
```

#### EKS:
```bash
# Scale the deployment
kubectl scale deployment forge-app --replicas=3 -n forge
```

## 6. Troubleshooting

### 6.1 Common Issues

1. Database Connection Issues:
```bash
# Check database connectivity
nc -zv ${RDS_ENDPOINT} 5432

# Check application logs for connection errors
docker logs forge-app
```

2. Application Health Issues:
```bash
# Check application health endpoint
curl -v http://localhost:8000/health

# Check Kubernetes events
kubectl get events -n forge
```

3. Resource Issues:
```bash
# Check EC2 instance metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/EC2 \
    --metric-name CPUUtilization \
    --dimensions Name=InstanceId,Value=<instance-id> \
    --start-time $(date -v-1H -u +%Y-%m-%dT%H:%M:%SZ) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --period 300 \
    --statistics Average
```

## 7. Cleanup

### 7.1 EC2 Cleanup
```bash
# Stop and remove containers
docker-compose -f docker-compose.prod.yml down

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids <instance-id>
```

### 7.2 EKS Cleanup
```bash
# Delete the deployment
kubectl delete -f k8s/ -n forge

# Delete the cluster
eksctl delete cluster --name forge-cluster --region <region>
```

### 7.3 RDS Cleanup
```bash
# Delete RDS instance
aws rds delete-db-instance \
    --db-instance-identifier forge-db \
    --skip-final-snapshot
```
