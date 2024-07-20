provider "aws" {
  region = "us-east-1" # or your preferred region
}

resource "aws_iam_role" "lambda_exec" {
  name = "lambda_exec_role"
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

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "slackbot" {
  filename         = "function.zip"
  function_name    = "slackbot"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "slack_bot.lambda_handler"
  runtime          = "python3.11"
  source_code_hash = filebase64sha256("function.zip")

  environment {
    variables = {
      SLACK_BOT_TOKEN = var.slack_bot_token
    }
  }
}

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
  function_name = aws_lambda_function.slackbot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.slackbot_api.execution_arn}/*/*"
}

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.slackbot_api.id
  resource_id             = aws_api_gateway_resource.lambda_resource.id
  http_method             = aws_api_gateway_method.lambda_method.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.slackbot.invoke_arn
}

resource "aws_api_gateway_deployment" "slackbot_deployment" {
  depends_on  = [aws_api_gateway_integration.lambda_integration]
  rest_api_id = aws_api_gateway_rest_api.slackbot_api.id
  stage_name  = "prod"
}

variable "slack_bot_token" {
  description = "Slack bot token"
  type        = string
}
