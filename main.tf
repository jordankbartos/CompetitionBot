provider "aws" {
  region = "us-east-1" # or your preferred region
}

data "aws_caller_identity" "current" {}

################# Secrets Manager ###########################
data "aws_secretsmanager_secret" "slack_bot_token" {
  name = "slack_bot_token"
}

data "aws_secretsmanager_secret_version" "slack_bot_token" {
  secret_id = data.aws_secretsmanager_secret.slack_bot_token.id
}

data "aws_secretsmanager_secret" "OPENAI_API_KEY" {
  name = "OPENAI_API_KEY"
}

data "aws_secretsmanager_secret_version" "OPENAI_API_KEY" {
  secret_id = data.aws_secretsmanager_secret.OPENAI_API_KEY.id
}

################## VPC ######################################
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "main_vpc"
  }
}

# Create public subnet
resource "aws_subnet" "public_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a" # Adjust based on your preference

  tags = {
    Name = "public_subnet_a"
  }
}
resource "aws_subnet" "public_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "us-east-1b" # Adjust based on your preference

  tags = {
    Name = "public_subnet_b"
  }
}
resource "aws_subnet" "public_c" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "us-east-1c" # Adjust based on your preference

  tags = {
    Name = "public_subnet_c"
  }
}
resource "aws_subnet" "public_d" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.4.0/24"
  availability_zone = "us-east-1d" # Adjust based on your preference

  tags = {
    Name = "public_subnet_d"
  }
}
resource "aws_subnet" "public_e" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.5.0/24"
  availability_zone = "us-east-1e" # Adjust based on your preference

  tags = {
    Name = "public_subnet_e"
  }
}
# Create Internet Gateway
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "main_igw"
  }
}

# Create a route table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "public_rt"
  }
}

# Associate route table with subnet
resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "c" {
  subnet_id      = aws_subnet.public_c.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "d" {
  subnet_id      = aws_subnet.public_d.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "e" {
  subnet_id      = aws_subnet.public_e.id
  route_table_id = aws_route_table.public.id
}


################# LAMBDA IAM ###########################
resource "aws_iam_role" "worker_lambda_exec" {
  name = "worker_lambda_exec_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Effect = "Allow",
      Sid    = ""
    }]
  })
}

resource "aws_iam_policy" "worker_lambda_policy" {
  name        = "worker_lambda_policy"
  description = "Allow lambda to write logs to CloudWatch and modify Cloudwatch events"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "events:PutRule",
        "events:PutTargets",
        "events:RemoveTargets",
        "events:DeleteRule",
        "events:ListTargetsByRule",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:GetPolicy",
        "lambda:InvokeFunction",
      ],
      Effect   = "Allow",
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "worker_lambda_policy" {
  role       = aws_iam_role.worker_lambda_exec.name
  policy_arn = aws_iam_policy.worker_lambda_policy.arn
}


resource "aws_iam_policy" "lambda_dynamodb_access_policy" {
  name = "lambda_dynamodb_access_policy"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = "arn:aws:dynamodb:us-east-1:${data.aws_caller_identity.current.account_id}:table/${aws_dynamodb_table.advice_table.name}"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb_policy_attachment" {
  role       = aws_iam_role.worker_lambda_exec.name
  policy_arn = aws_iam_policy.lambda_dynamodb_access_policy.arn
}


############# EventBridge Rule ##############################
resource "aws_cloudwatch_event_rule" "eb_trigger" {
  name                = "eb-worker_slackbot-trigger"
  description         = "Trigger the worker_slackbot lambda"
  schedule_expression = "cron(0 2 ? * 1 *)"
  state               = "ENABLED"
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "eb-worker_slackbot-trigger-permission"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker_slackbot.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.eb_trigger.arn
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.eb_trigger.name
  target_id = "worker_slackbot_lambda"
  arn       = aws_lambda_function.worker_slackbot.arn
}

########################### DYNAMODB #########################
resource "aws_dynamodb_table" "advice_table" {
  name         = "slackbot_advice"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "advice_id"

  attribute {
    name = "advice_id"
    type = "S"
  }

  tags = {
    Environment = "production"
    Purpose     = "Store advice history for slackbot"
  }
}

########################## LAMBDA ############################
resource "aws_lambda_function" "worker_slackbot" {
  filename         = "build/worker.zip"
  function_name    = "worker_slackbot"
  role             = aws_iam_role.worker_lambda_exec.arn
  handler          = "slack_bot.lambda_handler"
  runtime          = "python3.11"
  source_code_hash = filebase64sha256("build/worker.zip")
  timeout          = 30 # seconds

  environment {
    variables = {
      SLACK_BOT_TOKEN = data.aws_secretsmanager_secret_version.slack_bot_token.secret_string
      OPENAI_API_KEY  = data.aws_secretsmanager_secret_version.OPENAI_API_KEY.secret_string
      AWS_ACCOUNT_ID  = data.aws_caller_identity.current.account_id
      LOG_LEVEL       = "INFO"
      DYNAMODB_TABLE  = aws_dynamodb_table.advice_table.name
      # AWS_REGION      = "us-east-1"
    }
  }
}

resource "aws_lambda_function" "handler_slackbot" {
  filename         = "build/handler.zip"
  function_name    = "handler_slackbot"
  role             = aws_iam_role.worker_lambda_exec.arn # TODO RESTRICT THIS
  handler          = "request.request_handler"
  runtime          = "python3.11"
  source_code_hash = filebase64sha256("build/handler.zip")
  timeout          = 5 # seconds

}

################# API Gateway ###########################
resource "aws_api_gateway_rest_api" "slackbot_api" {
  name = "slackbot-api"
}

resource "aws_api_gateway_resource" "lambda_resource" {
  rest_api_id = aws_api_gateway_rest_api.slackbot_api.id
  parent_id   = aws_api_gateway_rest_api.slackbot_api.root_resource_id
  path_part   = "slackbot"
}

resource "aws_api_gateway_method" "lambda_method" {
  rest_api_id   = aws_api_gateway_rest_api.slackbot_api.id
  resource_id   = aws_api_gateway_resource.lambda_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.handler_slackbot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.slackbot_api.execution_arn}/*/*"
}

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.slackbot_api.id
  resource_id             = aws_api_gateway_resource.lambda_resource.id
  http_method             = aws_api_gateway_method.lambda_method.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.handler_slackbot.invoke_arn
}

resource "aws_api_gateway_deployment" "handler_slackbot_deployment" {
  depends_on  = [aws_api_gateway_integration.lambda_integration]
  rest_api_id = aws_api_gateway_rest_api.slackbot_api.id
  stage_name  = "prod"
}

