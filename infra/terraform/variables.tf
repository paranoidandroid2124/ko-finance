variable "project_id" {
  description = "GCP project id."
  type        = string
}

variable "project_prefix" {
  description = "Short prefix used for resource names."
  type        = string
  default     = "kfinance"
}

variable "region" {
  description = "Primary GCP region."
  type        = string
  default     = "asia-northeast3"
}

variable "container_image" {
  description = "Container image to deploy to Cloud Run."
  type        = string
}

variable "run_service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "kfinance-api"
}

variable "database_url" {
  description = "Database URL stored in Secret Manager."
  type        = string
  sensitive   = true
}

variable "sql_tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-custom-2-3840"
}

variable "database_name" {
  description = "Initial application database name."
  type        = string
  default     = "kfinance"
}

variable "database_user" {
  description = "Application database username."
  type        = string
  default     = "kfinance_app"
}

variable "database_password" {
  description = "Application database password."
  type        = string
  sensitive   = true
}
