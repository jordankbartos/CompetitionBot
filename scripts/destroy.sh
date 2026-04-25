set -ex

# Run terraform from the infra directory
cd infra
terraform destroy

# Clean up build artifacts
rm -rf ../build/*
