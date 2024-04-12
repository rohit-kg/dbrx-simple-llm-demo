# Databricks notebook source
dbutils.widgets.text("catalog", "dbdemos", "Data Catalog")
dbutils.widgets.text("customer_name", "newco", "Organization Name")
dbutils.widgets.text("pdf_link", "https://content.cdntwrk.com/files/aT0xMzkwNjczJnY9MiZpc3N1ZU5hbWU9dGhlLWZpdmV0cmFuLXByb3RvY29sLWVib29rJmNtZD1kJnNpZz0yOTQ3NzFhNmZhMDBjMzQyOWVhMmJjNDhjYmQ5Mzk2Yw%253D%253D", "Link to PDF to Start VS")
dbutils.widgets.text("vs_endpoint", "one-env-shared-endpoint-7", "VS Endpoint")

# COMMAND ----------

catalog = dbutils.widgets.get("catalog")
customer_name = dbutils.widgets.get("customer_name")
customer_name = customer_name.replace(' ', '_').lower()
pdf_link = dbutils.widgets.get("pdf_link")
VECTOR_SEARCH_ENDPOINT_NAME = dbutils.widgets.get("vs_endpoint") # TODO make sure the job takes this new Param


# COMMAND ----------

email = spark.sql('select current_user() as user').collect()[0]['user']
username = email.split('@')[0].replace('.', '_')
dbName = db = f"rag_chatbot_{username}_{customer_name}"
