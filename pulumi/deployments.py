import pulumi
import pulumi_kubernetes as k8s
import re
import os
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
            "path_type": "Prefix",  # Ensure pathType is specified
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
