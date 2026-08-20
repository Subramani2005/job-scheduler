from app import create_app, db
from app.models import User, Project, Queue, RetryPolicy, Worker, Job, JobExecution, DeadLetterQueue

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port = 5000)