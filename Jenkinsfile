pipeline {
    agent any

    environment {
        IMAGE_NAME = "coreapi"
        CONTAINER_NAME = "coreapi-container"
        PORT = "8000"
    }

    stages {

        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    echo "Installing dependencies and running tests..."
                    docker run --rm -v "$PWD":/app -w /app python:3.12-slim-bookworm sh -c "
                        pip install --no-cache-dir -r requirements.txt &&
                        python manage.py test
                    "
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    echo "Building Docker image..."
                    docker build -t $IMAGE_NAME .
                '''
            }
        }

        stage('Run Container') {
            steps {
                sh '''
                    echo "Stopping old container if exists..."
                    docker rm -f $CONTAINER_NAME || true

                    echo "Starting new container..."
                    docker run -d --name $CONTAINER_NAME -p $PORT:8000 $IMAGE_NAME
                '''
            }
        }
    }

    post {
        success {
            echo "Build SUCCESS: Backend is running on port 8000"
        }

        failure {
            echo "Build FAILED: Check logs"
        }

        always {
            echo "Cleaning up unused Docker resources..."
            sh 'docker system prune -f || true'
        }
    }
}