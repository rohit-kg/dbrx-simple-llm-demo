# Databricks notebook source
# MAGIC %run ../config

# COMMAND ----------

vol_path = f"/Volumes/{catalog}/{dbName}/raw_document_landing_zone/"

# COMMAND ----------

# Drop the checkpoints
dbutils.fs.rm(vol_path+ "checkpoints/", recurse=True)

# COMMAND ----------

# drop all pdfs except for the initial pdf
files = dbutils.fs.ls(vol_path)

for file in files:
    # Get the file name
    file_name = file.name

    # Check if the file is not named "first_pdf.pdf"
    if file_name != "first_pdf.pdf" and ".pdf" in file_name:
        # Delete the file
        dbutils.fs.rm(file.path)

# COMMAND ----------

spark.sql(f"TRUNCATE TABLE {catalog}.{dbName}.pdf_raw")
spark.sql(f"TRUNCATE TABLE {catalog}.{dbName}.databricks_pdf_documentation")
