terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_service_account" "run" {
  account_id   = "${var.project_prefix}-api"
  display_name = "K-Finance Cloud Run"
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.project_prefix}-database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = var.database_url
}

resource "google_sql_database_instance" "primary" {
  name             = "${var.project_prefix}-pg"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = var.sql_tier
    backup_configuration {
      enabled = true
    }
  }
}

resource "google_sql_database" "app" {
  name     = var.database_name
  instance = google_sql_database_instance.primary.name
}

resource "google_sql_user" "app" {
  name     = var.database_user
  instance = google_sql_database_instance.primary.name
  password = var.database_password
}

resource "google_cloud_run_v2_service" "api" {
  name     = var.run_service_name
  location = var.region

  template {
    service_account = google_service_account.run.email
    containers {
      image = var.container_image
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.name
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    percent = 100
  }
}

resource "google_cloud_scheduler_job" "ingest_ping" {
  name        = "${var.project_prefix}-ingest-ping"
  description = "Periodic ping to keep ingest warm"
  schedule    = "*/30 * * * *"

  http_target {
    http_method = "GET"
    uri         = "${google_cloud_run_v2_service.api.uri}/healthz"
    oidc_token {
      service_account_email = google_service_account.run.email
    }
  }
}
