import boto3
import os

def init_db():
    endpoint_url = os.environ.get("DYNAMODB_URL", "http://localhost:8000")
    table_name = os.environ.get("DYNAMODB_TABLE", "poker_bot_data")
    
    dynamodb = boto3.client("dynamodb", endpoint_url=endpoint_url)
    
    try:
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        print(f"Table {table_name} created successfully.")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"Table {table_name} already exists.")

if __name__ == "__main__":
    init_db()
