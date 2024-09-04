import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
import re
import os
import json
from datetime import datetime

# Function to get the absolute path to the BUCKETS file
def get_absolute_path(file_name):
    current_directory = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_directory, '..', file_name)

# Function to read bucket names from the BUCKETS file
def get_bucket_names_from_file(file_name):
    file_path = get_absolute_path(file_name)
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]

# Function to sanitize names for Kubernetes compatibility
def sanitize_name(name):
    return re.sub(r'[^a-z0-9-]', '-', name.lower())

# Define the EKS cluster name
cluster_name = "Raviv-EKS-a92d7a9"

# Fetch the existing EKS cluster using get method
cluster = aws.eks.Cluster.get(cluster_name, cluster_name)

# Fetch the region and account ID
region = aws.get_region().name
account_id = aws.get_caller_identity().account_id
cluster_id = cluster.id

# Create the correct OIDC provider domain name for EKS
oidc_provider_domain = pulumi.Output.concat(
    "oidc.eks.", region, ".amazonaws.com/id/", cluster_id
)

# Create the IAM role with the corrected OIDC provider domain
role = aws.iam.Role("S3FullAccessRole",
    assume_role_policy=oidc_provider_domain.apply(lambda domain: json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Federated": f"arn:aws:iam::{account_id}:oidc-provider/{domain}"
                },
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        f"{domain}:sub": "system:serviceaccount:default:s3-full-access",
                        f"{domain}:aud": "sts.amazonaws.com"
                    }
                }
            }
        ]
    }))
)

# Attach the AmazonS3FullAccess policy to the role
role_policy_attachment = aws.iam.RolePolicyAttachment("s3FullAccessAttachment",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
)

# Create a Kubernetes Service Account with IAM role
service_account = k8s.core.v1.ServiceAccount("s3FullAccessServiceAccount",
    metadata={
        "name": "s3-full-access",
        "namespace": "default",
        "annotations": {
            "eks.amazonaws.com/role-arn": role.arn
        }
    }
)

# Function to create deployments, services, and a shared ingress resource
def create_deployments_services_and_ingress(bucket_file_name, provider):
    bucket_names = get_bucket_names_from_file(bucket_file_name)
    deployments = []
    services = []
    timestamp = datetime.now().isoformat()

    # Define the rules for the shared Ingress
    ingress_rules = []

    for i, bucket_name in enumerate(bucket_names):
        sanitized_name = sanitize_name(bucket_name)
        port = 1000 + i

        # Create Deployment
        deployment = k8s.apps.v1.Deployment(f"deployment-{sanitized_name}",
            metadata={
                "name": sanitized_name,
                "labels": {
                    "app": sanitized_name
                }
            },
            spec={
                "selector": {
                    "match_labels": {
                        "app": sanitized_name
                    }
                },
                "replicas": 1,
                "template": {
                    "metadata": {
                        "labels": {
                            "app": sanitized_name
                        },
                        "annotations": {
                            "version": timestamp
                        }
                    },
                    "spec": {
                        "service_account_name": "s3-service-account",  # Use the service account here
                        "containers": [{
                            "name": f"container-{sanitized_name}",
                            "image": "905418187602.dkr.ecr.us-west-2.amazonaws.com/unleash-task:latest",
                            "image_pull_policy": "Always",
                            "env": [
                                {"name": "BUCKET_NAME", "value": sanitized_name},
                                {"name": "PORT", "value": str(port)}
                            ],
                            "ports": [{"container_port": port}]
                        }]
                    }
                }
            },
            opts=pulumi.ResourceOptions(provider=provider)
        )
        deployments.append(deployment)

        # Create Service
        service = k8s.core.v1.Service(f"service-{sanitized_name}",
            metadata={
                "name": sanitized_name,
            },
            spec={
                "selector": {
                    "app": sanitized_name,
                },
                "ports": [{
                    "port": port,
                    "target_port": port
                }],
                "type": "ClusterIP"
            },
            opts=pulumi.ResourceOptions(provider=provider)
        )
        services.append(service)

        # Add rule for this service
        ingress_rules.append({
            "path": f"/{sanitized_name}",
            "path_type": "Prefix",
            "backend": {
                "service": {
                    "name": sanitized_name,
                    "port": {
                        "number": port
                    }
                }
            }
        })

    # Create a single Ingress resource
    ingress = k8s.networking.v1.Ingress("shared-ingress",
        metadata={
            "name": "shared-ingress",
            "namespace": "default",
            "annotations": {
                "alb.ingress.kubernetes.io/scheme": "internet-facing",
                "alb.ingress.kubernetes.io/target-type": "ip",
            }
        },
        spec={
            "ingress_class_name": "alb",
            "rules": [
                {
                    "http": {
                        "paths": ingress_rules
                    }
                }
            ]
        },
        opts=pulumi.ResourceOptions(provider=provider)
    )

    return deployments, services, ingress
