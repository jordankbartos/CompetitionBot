import os
import time

import boto3
from botocore.exceptions import EndpointConnectionError


def init_db():
    endpoint_url = os.environ.get("DYNAMODB_URL", "http://localhost:8000")
    table_name = os.environ.get("DYNAMODB_TABLE", "poker_bot_data")

    # For local dev, provide dummy credentials if not found
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )

    # Wait for DynamoDB to be ready
    max_retries = 5
    for i in range(max_retries):
        try:
            dynamodb.list_tables()
            break
        except EndpointConnectionError:
            if i == max_retries - 1:
                print(
                    f"Error: Could not connect to DynamoDB at {endpoint_url} after {max_retries} retries."
                )
                return
            print(f"Waiting for DynamoDB at {endpoint_url}... (attempt {i+1}/{max_retries})")
            time.sleep(2)

    try:
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Table {table_name} created successfully.")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"Table {table_name} already exists.")
    except Exception as e:
        print(f"Failed to create table: {e}")


if __name__ == "__main__":
    init_db()
