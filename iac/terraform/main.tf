resource "kubernetes_pod" "RmonNetApp" {
  metadata {
    name = "RmonNetApp"
    namespace = "evolved5g"
    labels = {
      app = "example"
    }
  }

  spec {
    container {
      image = "dockerhub.hi.inet/evolved-5g/RmonNetApp:latest"
      name  = "rmonnetapp"
    }
  }
}

resource "kubernetes_service" "RmonNetApp_service" {
  metadata {
    name = "example-rmonnetapp-service"
    namespace = "evolved5g"
  }
  spec {
    selector = {
      app = kubernetes_pod.example.metadata.0.labels.app
    }
    port {
      port = 80
      target_port = 80
    }
  }
}
