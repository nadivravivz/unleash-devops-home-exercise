import pulumi
import pulumi_aws as aws

# Define the ECR repository with additional settings
unleash_task_repo = aws.ecr.Repository("unleash-task",
    name="unleash-task",
    image_tag_mutability="MUTABLE",
    image_scanning_configuration={
        "scan_on_push": True,
    })

# Export the repository URL and repository ARN
pulumi.export("repository_url", unleash_task_repo.repository_url)
pulumi.export("repository_arn", unleash_task_repo.arn)
