# CompetitionBot Project

This project contains the infrastructure and code for the CompetitionBot.

## Deployment

The deployment of this project is managed using Terraform. The `deploy.sh` script is used to initialize and apply the Terraform configuration.

### AWS Authentication

The `deploy.sh` script is configured to use a specific AWS CLI profile for authentication. This is crucial for ensuring that the deployment operations are performed with the correct permissions.

**Required AWS Profile:** `compbot-dev`

Before running `deploy.sh`, ensure that you have an AWS CLI profile named `compbot-dev` configured in your `~/.aws/credentials` file. This profile should contain the access key ID and secret access key for the AWS user or role that has the necessary permissions to deploy the resources defined in `main.tf`.

**Example `~/.aws/credentials` entry:**

```ini
[compbot-dev]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

The `deploy.sh` script explicitly sets the `AWS_PROFILE` environment variable to `compbot-dev` before executing Terraform commands:

```bash
export AWS_PROFILE="compbot-dev"
terraform init
terraform apply -auto-approve
```

This ensures that Terraform uses the credentials from the `compbot-dev` profile, preventing permission errors (e.g., 403 Forbidden) that might occur if default or incorrect credentials were used.

## Build Process

The `build.sh` script is responsible for packaging the Lambda functions. It performs the following steps:
1. Cleans up existing build artifacts.
2. Creates necessary package directories.
3. Copies Python scripts to the package directories.
4. Installs Python dependencies into the package directories.
5. Creates ZIP files for the worker and handler Lambda functions.
