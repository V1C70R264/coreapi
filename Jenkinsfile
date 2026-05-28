pipeline {
agent any

```
stages {

    stage('Checkout Code') {
        steps {
            checkout scm
        }
    }

    stage('Verify Python') {
        steps {
            sh 'python3 --version || python --version'
        }
    }

    stage('Install Dependencies') {
        steps {
            sh '''
                pip3 install -r requirements.txt || pip install -r requirements.txt
            '''
        }
    }

    stage('Run Django Tests') {
        steps {
            sh '''
                python3 manage.py test || python manage.py test
            '''
        }
    }

}

post {

    success {
        echo 'Pipeline executed successfully!'
    }

    failure {
        echo 'Pipeline failed!'
    }
}
```

}
