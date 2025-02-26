//////////////////////////////////////
// Variable Declarations
//////////////////////////////////////
variable "wandb_key" {
  description = "The wandb_key"
  type        = string
}

data "google_project" "project" {}

# Artifact Registry for storing Docker images
resource "google_artifact_registry_repository" "repo" {
  provider = google
  location      = "us-west1"
  repository_id = "ni-sn27-repo"
  format        = "DOCKER"
}


# Build and Push Docker Images
resource "null_resource" "build_push_images" {
  provisioner "local-exec" {
    command = <<EOT
      gcloud auth configure-docker us-west1-docker.pkg.dev
      docker build -t us-west1-docker.pkg.dev/ni-sn27-streamlit-prod/ni-sn27-repo/frontend:latest -f frontend.Dockerfile .
      docker push us-west1-docker.pkg.dev/ni-sn27-streamlit-prod/ni-sn27-repo/frontend:latest
      docker build -t us-west1-docker.pkg.dev/ni-sn27-streamlit-prod/ni-sn27-repo/backend:latest -f backend.Dockerfile .
      docker push us-west1-docker.pkg.dev/ni-sn27-streamlit-prod/ni-sn27-repo/backend:latest
    EOT
  }
  triggers = {
    timestamp = "${timestamp()}"
  }
}

# Cloud Run Service for Backend
resource "google_cloud_run_service" "backend" {
  name     = "opencompute-backend"
  location = "us-west1"

  template {
    spec {
      containers {
        image = "us-west1-docker.pkg.dev/ni-sn27-streamlit-prod/ni-sn27-repo/backend:latest"
        ports {
          container_port = 8316
          name           = "http1"
        }
        env {
          name  = "WANDB_API_KEY"
          value = var.wandb_key
        }
      }
    }
  }
  depends_on = [null_resource.build_push_images]
}

# Cloud Run Service for Frontend
resource "google_cloud_run_service" "frontend" {
  name     = "opencompute-frontend"
  location = "us-west1"

  template {
    spec {
      containers {
        image = "us-west1-docker.pkg.dev/ni-sn27-streamlit-prod/ni-sn27-repo/frontend:latest"
        ports {
          container_port = 80
          name           = "http1"
        }
        env {
          name  = "BACKEND_URL"
          value = "opencompute-backend-${data.google_project.project.number}.us-west1.run.app"
        }
      }
    }
  }
  depends_on = [null_resource.build_push_images]
}

# Allow unauthenticated access (optional, restrict if needed)
resource "google_cloud_run_service_iam_member" "frontend_invoker" {
  service  = google_cloud_run_service.frontend.name
  location = google_cloud_run_service.frontend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "backend_invoker" {
  service  = google_cloud_run_service.backend.name
  location = google_cloud_run_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
