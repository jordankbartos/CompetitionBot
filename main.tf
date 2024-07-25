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

data "aws_secretsmanager_secret" "db_password" {
  name = "db_password"
}

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = data.aws_secretsmanager_secret.db_password.id
}

data "aws_secretsmanager_secret" "db_username" {
  name = "db_username"
}

data "aws_secretsmanager_secret_version" "db_username" {
  secret_id = data.aws_secretsmanager_secret.db_username.id
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
################# Security Groups ###########################
resource "aws_security_group" "slackbot_sg" {
  name        = "slackbot_sg"
  description = "Allow MySQL inbound traffic"
  vpc_id      = aws_vpc.main.id # replace with your VPC ID

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"] # replace with your IP address
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Create a DB subnet group
resource "aws_db_subnet_group" "main" {
  name       = "main"
  subnet_ids = [aws_subnet.public_a.id, aws_subnet.public_b.id, aws_subnet.public_c.id, aws_subnet.public_d.id, aws_subnet.public_e.id]

  tags = {
    Name = "main_db_subnet_group"
  }
}

################# RDS DB ###########################

resource "aws_db_instance" "slackbot_db" {
  allocated_storage      = 20
  storage_type           = "gp2"
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = "db.t3.micro"
  username               = data.aws_secretsmanager_secret_version.db_username.secret_string
  password               = data.aws_secretsmanager_secret_version.db_password.secret_string
  parameter_group_name   = "default.mysql8.0"
  skip_final_snapshot    = true
  publicly_accessible    = true
  vpc_security_group_ids = [aws_security_group.slackbot_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  tags = {
    Name = "slackbot_db"
  }
}

resource "null_resource" "apply_schema" {
  depends_on = [aws_db_instance.slackbot_db]

  provisioner "local-exec" {
    command = <<EOF
      DB_HOST=$(echo ${aws_db_instance.slackbot_db.endpoint} | sed 's/:3306//')
      mysql -h $DB_HOST -u ${data.aws_secretsmanager_secret_version.db_username.secret_string} -p${data.aws_secretsmanager_secret_version.db_password.secret_string} -e "
      CREATE DATABASE IF NOT EXISTS slackbot_db;
      USE slackbot_db;
      CREATE TABLE IF NOT EXISTS CompetitionTypes (
        competition_type_id INT AUTO_INCREMENT PRIMARY KEY,
        type_name VARCHAR(255) NOT NULL
      );
      CREATE TABLE IF NOT EXISTS LogParameters (
        parameter_id INT AUTO_INCREMENT PRIMARY KEY,
        parameter_name VARCHAR(255) NOT NULL UNIQUE
      );
      CREATE TABLE IF NOT EXISTS Competitors (
        competitor_id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL
      );
      CREATE TABLE IF NOT EXISTS Logs (
        log_id INT AUTO_INCREMENT PRIMARY KEY,
        log_datetime DATETIME NOT NULL,
        competitor_id INT NOT NULL,
        calories_burned INT DEFAULT NULL,
        number_of_workouts INT DEFAULT NULL,
        workout_time INT DEFAULT NULL,
        weight_lost DECIMAL(5, 2) DEFAULT NULL,
        FOREIGN KEY (competitor_id) REFERENCES Competitors(competitor_id)
      );
      CREATE TABLE IF NOT EXISTS Competitions (
        competition_id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL UNIQUE,
        start_datetime DATETIME NOT NULL,
        end_datetime DATETIME NOT NULL,
        competition_type_id INT NOT NULL,
        FOREIGN KEY (competition_type_id) REFERENCES CompetitionTypes(competition_type_id)
      );
      CREATE TABLE IF NOT EXISTS CompetitionLogs (
        competition_id INT NOT NULL,
        log_id INT NOT NULL,
        PRIMARY KEY (competition_id, log_id),
        FOREIGN KEY (competition_id) REFERENCES Competitions(competition_id),
        FOREIGN KEY (log_id) REFERENCES Logs(log_id)
      );
      CREATE TABLE IF NOT EXISTS CompetitionTypeParameters (
        competition_type_id INT NOT NULL,
        parameter_id INT NOT NULL,
        PRIMARY KEY (competition_type_id, parameter_id),
        FOREIGN KEY (competition_type_id) REFERENCES CompetitionTypes(competition_type_id),
        FOREIGN KEY (parameter_id) REFERENCES LogParameters(parameter_id)
      );"
    EOF
  }
}

################# LAMBDA ###########################

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

resource "aws_iam_policy" "lambda_policy" {
  name        = "lambda_policy"
  description = "Allow lambda to write logs to CloudWatch"
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
      ],
      Effect   = "Allow",
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}



############# EventBridge Rule ##############################
resource "aws_cloudwatch_event_rule" "eb_trigger" {
  name                = "eb-slackbot-trigger"
  description         = "Trigger the slackbot lambda"
  schedule_expression = "cron(*/3 * * * ? *)"
  # schedule_expression = "cron(0 0 */4 * ? *)"
  state = "ENABLED"
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "eb-slackbot-trigger-permission"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slackbot.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.eb_trigger.arn
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.eb_trigger.name
  target_id = "slackbot_lambda"
  arn       = aws_lambda_function.slackbot.arn
}

########################## lambda ############################
resource "aws_lambda_function" "slackbot" {
  filename         = "function.zip"
  function_name    = "slackbot"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "slack_bot.lambda_handler"
  runtime          = "python3.11"
  source_code_hash = filebase64sha256("function.zip")
  timeout          = 30 # seconds

  environment {
    variables = {
      SLACK_BOT_TOKEN = data.aws_secretsmanager_secret_version.slack_bot_token.secret_string
      DB_HOST         = aws_db_instance.slackbot_db.endpoint
      DB_NAME         = "slackbot_db"
      DB_USERNAME     = data.aws_secretsmanager_secret_version.db_username.secret_string
      DB_PASSWORD     = data.aws_secretsmanager_secret_version.db_password.secret_string
      OPENAI_API_KEY  = data.aws_secretsmanager_secret_version.OPENAI_API_KEY.secret_string
      AWS_ACCOUNT_ID  = data.aws_caller_identity.current.account_id
      LOG_LEVEL       = "INFO"
    }
  }
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

