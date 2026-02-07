set -ex

# Set the AWS profile to use for this script
export AWS_PROFILE="compbot-dev"

terraform init
terraform apply -auto-approve
