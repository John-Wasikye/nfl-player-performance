terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Native S3 locking (use_lockfile) needs no DynamoDB table. Create the bucket with infra/bootstrap first.
  backend "s3" {
    bucket       = "jw-nfl-player-stats-tfstate"
    key          = "nfl-player-performance/terraform.tfstate"
    region       = "us-east-1"
    profile      = "nfl_player_stats"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region  = var.region
  profile = var.profile

  default_tags {
    tags = {
      Project   = "nfl-player-performance"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
