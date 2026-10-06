variable "region" {
  type    = string
  default = "us-east-1"
}

variable "profile" {
  type    = string
  default = "nfl_player_stats"
}

variable "bucket_prefix" {
  description = "Globally unique prefix for every bucket. Underscores are illegal in S3 names."
  type        = string
  default     = "jw-nfl-player-stats"
}

variable "records_retention_days" {
  description = "Default Object Lock retention for locked predictions and the ledger (governance mode)."
  type        = number
  default     = 365
}

variable "raw_noncurrent_days" {
  type    = number
  default = 30
}

variable "site_noncurrent_days" {
  type    = number
  default = 14
}

variable "ecr_images_kept" {
  type    = number
  default = 10
}

variable "task_cpu" {
  type    = number
  default = 2048
}

variable "task_memory" {
  type    = number
  default = 8192
}

variable "image_tag" {
  description = "ECR tags are immutable, so every pushed image needs a new tag."
  type        = string
  default     = "v4"
}
