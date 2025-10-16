terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "project_name" {
  type        = string
  description = "Project identifier used for tagging resources."
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "us-east-1"
}

variable "container_port" {
  type        = number
  description = "Port exposed by the application container."
  default     = 80
}

resource "aws_ecr_repository" "mailbot" {
  name                 = "${var.project_name}-repo"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecs_cluster" "mailbot" {
  name = "${var.project_name}-cluster"
}

resource "aws_ecs_task_definition" "mailbot" {
  family                   = "${var.project_name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"

  container_definitions = jsonencode([
    {
      name      = "mailbot"
      image     = "${aws_ecr_repository.mailbot.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
        }
      ]
      environment = [
        {
          name  = "APP_PORT"
          value = tostring(var.container_port)
        }
      ]
    }
  ])
}

output "ecr_repository_url" {
  value = aws_ecr_repository.mailbot.repository_url
}
