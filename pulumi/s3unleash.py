import pulumi
import pulumi_aws as aws
import os
import re

# Function to get the absolute path to the BUCKETS file
def get_absolute_path(file_name):
    current_directory = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_directory, '..', file_name)

# Function to read bucket names from the BUCKETS file
def get_bucket_names_from_file(file_name):
    file_path = get_absolute_path(file_name)
    with open(file_path, 'r') as file:
        return [line.strip() for line in file.readlines() if line.strip()]

# Function to sanitize bucket names for AWS S3 compatibility
def sanitize_bucket_name(name):
    # S3 bucket names must be globally unique and follow certain rules
    return re.sub(r'[^a-z0-9-]', '-', name.lower())

# Function to create S3 buckets
def create_s3_buckets(bucket_file_name):
    bucket_names = get_bucket_names_from_file(bucket_file_name)
    s3_buckets = []

    for bucket_name in bucket_names:
        sanitized_name = sanitize_bucket_name(bucket_name)

        # Create S3 Bucket
        bucket = aws.s3.Bucket(sanitized_name,
            bucket=sanitized_name,
            acl="private",  # Adjust the ACL as needed
            opts=pulumi.ResourceOptions(
                # You might want to use some additional options here
            )
        )
        s3_buckets.append(bucket)

    return s3_buckets