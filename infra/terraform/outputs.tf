output "cloud_run_service_url" {
  description = "Deployed Cloud Run service URL."
  value       = google_cloud_run_v2_service.api.uri
}

output "cloud_sql_instance_connection_name" {
  description = "Cloud SQL instance connection string used by Cloud Run."
  value       = google_sql_database_instance.primary.connection_name
}
