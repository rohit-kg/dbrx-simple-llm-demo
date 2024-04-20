# Databricks notebook source
# MAGIC %md This Notebook Creates the Workflow with the Databricks SDK

# COMMAND ----------

# MAGIC %pip install databricks-sdk --upgrade
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./config

# COMMAND ----------

volume_folder =  f"/Volumes/{catalog}/{db}/raw_document_landing_zone/"

# COMMAND ----------

# Create workspace client
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# COMMAND ----------

# identify cloud & select appropriate cluster type
from databricks.sdk.service.jobs import JobCluster

cluster_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterId")
if w.clusters.get(cluster_id).aws_attributes is not None:
    cluster_type = "i3.xlarge"
elif w.clusters.get(cluster_id).azure_attributes is not None:
    cluster_type = "Standard_E4d_v4"
else:
    print("Could not determine cloud type based on this cluster. Make sure you're running with a regular cluster, not a serverless one")
    
job_cluster_dict = {
    "job_cluster_key": "Job_cluster",
    "new_cluster": {
        "cluster_name": "",
        "spark_version": "14.3.x-scala2.12",
        "node_type_id": cluster_type,
        "data_security_mode": "SINGLE_USER",
        "runtime_engine": "STANDARD",
        "num_workers": 1,
    },
}

# COMMAND ----------

# Define the job configuration JSON and convert to Job object
from databricks.sdk.service.jobs import CreateJob

job_config = {
    "run_as": {"user_name": email},
    "job_clusters": [job_cluster_dict],
    "trigger": {"file_arrival": {"url": f'{volume_folder}'}},
    "tasks": [
        {
            "task_key": "01-Document-Ingestion-and-Index-Creation",
            "run_if": "ALL_SUCCESS",
            "notebook_task": {
                "notebook_path": "01-Data-Preparation-and-Index",
                "source": "GIT",
            },
            "job_cluster_key": "Job_cluster",
        },
        {
            "task_key": "01-Streaming-Document-Ingestion",
            "depends_on": [{"task_key": "01-Document-Ingestion-and-Index-Creation"}],
            "run_if": "ALL_SUCCESS",
            "notebook_task": {
                "notebook_path": "01-Streaming-Data-Preparation",
                "source": "GIT",
            },
            "job_cluster_key": "Job_cluster",
        },
        {
            "task_key": "02-Deploy-RAG-Chatbot-Model",
            "depends_on": [{"task_key": "01-Document-Ingestion-and-Index-Creation"}],
            "run_if": "ALL_SUCCESS",
            "notebook_task": {
                "notebook_path": "02-Deploy-RAG-Chatbot-Model",
                "source": "GIT",
            },
            "job_cluster_key": "Job_cluster",
        },
        {
            "task_key": "03-Deploy-RAG-Chatbot",
            "depends_on": [{"task_key": "02-Deploy-RAG-Chatbot-Model"}],
            "run_if": "ALL_SUCCESS",
            "notebook_task": {
                "notebook_path": "03-RAG-Gradio-App",
                "base_parameters": {"workspace_id": "{{workspace.id}}"},
                "source": "GIT",
            },
            "job_cluster_key": "Job_cluster",
        },
        {
            "task_key": "03-Deploy-Simple-chatbot",
            "depends_on": [{"task_key": "02-Deploy-RAG-Chatbot-Model"}],
            "run_if": "ALL_SUCCESS",
            "notebook_task": {
                "notebook_path": "03-No-RAG-Gradio-App",
                "base_parameters": {"workspace_id": "{{workspace.id}}"},
                "source": "GIT",
            },
            "job_cluster_key": "Job_cluster",
        },
    ],
    "git_source": {
        "git_url": "https://github.com/rohit-kg/dbrx-simple-llm-demo/",
        "git_provider": "gitHub",
        "git_branch": "main",
    },
    "parameters": [
        {"name": "catalog", "default": "dbdemos"},
        {"name": "customer_name", "default": "newco"},
        {
            "name": "pdf_link",
            "default": "https://content.cdntwrk.com/files/aT0xMzkwNjczJnY9MiZpc3N1ZU5hbWU9dGhlLWZpdmV0cmFuLXByb3RvY29sLWVib29rJmNtZD1kJnNpZz0yOTQ3NzFhNmZhMDBjMzQyOWVhMmJjNDhjYmQ5Mzk2Yw%253D%253D",
        },
        {"name": "skip_setup", "default": "false"},
    ],
}

new_job = CreateJob.from_dict(job_config)

# COMMAND ----------

from databricks.sdk.service.jobs import Task, NotebookTask, Source, TaskDependency

j = w.jobs.create(
    name=f"({username}) mfg_llm_demo",
    tasks=new_job.tasks,
    trigger = new_job.trigger,
    git_source=new_job.git_source,
    job_clusters=new_job.job_clusters,
    parameters=new_job.parameters,
    run_as=new_job.run_as,
)

# COMMAND ----------

# delete job
job_id = [i for i in w.jobs.list(name=f"({username}) mfg_llm_demo")][0].job_id
w.jobs.delete(job_id=job_id)
