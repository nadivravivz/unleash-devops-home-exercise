import pulumi
import ecr_unleash
import pulumi_kubernetes as k8s
import pulumi_aws as aws
import deployments
import s3unleash

# Load network configuration from Pulumi config
config = pulumi.Config()
vpc_id = config.require("vpc_id")
subnet_ids = config.require_object("subnet_ids")
security_group_ids = config.require_object("security_group_ids")

# Create an IAM role for EKS
role = aws.iam.Role("eksRole",
    assume_role_policy=pulumi.Output.json_dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "eks.amazonaws.com",
                },
            },
        ],
    })
)

# Attach the AmazonEKSClusterPolicy policy to the role
role_policy_attachment = aws.iam.RolePolicyAttachment("eksRolePolicyAttachment",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
)

# Define the IAM Role for EKS nodes
node_role = aws.iam.Role("nodeRole",
    assume_role_policy=pulumi.Output.json_dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com",
                },
            },
        ],
    })
)

# Define policies required for EKS nodes
node_instance_policies = [
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
]

# Attach policies to the IAM Role for EKS nodes
for index, policy_arn in enumerate(node_instance_policies):
    aws.iam.RolePolicyAttachment(f"nodeRolePolicyAttachment{index}",
        role=node_role.name,
        policy_arn=policy_arn
    )

# Create an EKS cluster
cluster = aws.eks.Cluster("Raviv-EKS",
    role_arn=role.arn,
    vpc_config={
        "subnet_ids": subnet_ids,
        "security_group_ids": security_group_ids,
    },
    access_config={
        "authentication_mode": "API_AND_CONFIG_MAP",
        "bootstrap_cluster_creator_admin_permissions": True
    }
)

# Create a node group with one instance
node_group = aws.eks.NodeGroup("Raviv-Node",
    cluster_name=cluster.name,
    node_role_arn=node_role.arn,
    subnet_ids=subnet_ids,
    scaling_config={
        "desired_size": 3,
        "max_size": 3,
        "min_size": 1,
    },
    instance_types=["t3.large"],  # Choose instance type
)

k8s_provider = k8s.Provider("k8sProvider",)

s3unleash.create_s3_buckets("BUCKETS")

deployments.create_deployments_services_and_ingress('BUCKETS',provider=k8s_provider)

# Access and print the ECR exported outputs directly
repo_url = ecr_unleash.unleash_task_repo.repository_url
repo_arn = ecr_unleash.unleash_task_repo.arn

pulumi.export("cluster_name", cluster.name)
pulumi.export("cluster_endpoint", cluster.endpoint)
print(f"Repository URL: {repo_url}")
print(f"Repository ARN: {repo_arn}")