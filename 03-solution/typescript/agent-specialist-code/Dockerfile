FROM public.ecr.aws/docker/library/python:3.11-slim
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN pip install aws-opentelemetry-distro>=0.10.1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

# The orchestrator serves HTTP on 8080; the specialist serves A2A on 9000.
EXPOSE 8080
EXPOSE 9000

COPY . .

CMD ["opentelemetry-instrument", "python", "-m", "agent"]
