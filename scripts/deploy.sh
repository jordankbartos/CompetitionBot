set -ex

# Set the AWS profile to use for this script
export AWS_PROFILE="compbot-dev"

# Run terraform from the infra directory
cd infra
terraform init
terraform apply -auto-approve
