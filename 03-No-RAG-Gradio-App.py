# Databricks notebook source
# MAGIC %pip install --upgrade gradio==3.38.0 fastapi==0.104 uvicorn==0.24
# MAGIC %pip install typing-extensions==4.8.0 --upgrade
# MAGIC %pip install -q -U langchain==0.0.319
# MAGIC %pip install --force-reinstall databricks-genai-inference==0.1.1
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ./_resources/00-init $reset_all_data=false

# COMMAND ----------

# MAGIC %md ### Helper functions

# COMMAND ----------

# DBTITLE 1,Setup authentication for our model
# url used to send the request to your model from the serverless endpoint
host = "https://" + spark.conf.get("spark.databricks.workspaceUrl")
os.environ['DATABRICKS_TOKEN'] = dbutils.secrets.get("dbdemos", "rag_sp_token")

# COMMAND ----------

# Test Databricks Foundation LLM model
from langchain_community.chat_models import ChatDatabricks
chat_model = ChatDatabricks(endpoint="databricks-dbrx-instruct", max_tokens = 200)
# print(f"Test chat model: {chat_model.predict('How can I make my data ingestion API efficient?', max_tokens=150)}")

# COMMAND ----------

def generate_output(message: str,
        chat_history: list[tuple[str, str]]):
    
    chat_model = ChatDatabricks(endpoint="databricks-dbrx-instruct", max_tokens = 200)
    output = chat_model.predict(message, max_tokens=150)
    return output

# COMMAND ----------

result = generate_output("How can I make my data ingestion API efficient?", [])

displayHTML(result)

# COMMAND ----------

# MAGIC %md 
# MAGIC ### Let's host it in gradio

# COMMAND ----------

import json
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI

# COMMAND ----------

@dataclass
class ProxySettings:
    proxy_url: str
    port: str
    url_base_path: str


class DatabricksApp:

    def __init__(self, port):
        # self._app = data_app
        self._port = port
        import IPython
        self._dbutils = IPython.get_ipython().user_ns["dbutils"]
        self._display_html = IPython.get_ipython().user_ns["displayHTML"]
        self._context = json.loads(self._dbutils.notebook.entry_point.getDbutils().notebook().getContext().toJson())
        # need to do this after the context is set
        self._cloud = self.get_cloud()
        # create proxy settings after determining the cloud
        self._ps = self.get_proxy_settings()
        self._fastapi_app = self._make_fastapi_app(root_path=self._ps.url_base_path.rstrip("/"))
        self._streamlit_script = None
        # after everything is set print out the url

    def _make_fastapi_app(self, root_path) -> FastAPI:
        fast_api_app = FastAPI(root_path=root_path)

        @fast_api_app.get("/")
        def read_main():
            return {
                "routes": [
                    {"method": "GET", "path": "/", "summary": "Landing"},
                    {"method": "GET", "path": "/status", "summary": "App status"},
                    {"method": "GET", "path": "/dash", "summary": "Sub-mounted Dash application"},
                ]
            }

        @fast_api_app.get("/status")
        def get_status():
            return {"status": "ok"}

        return fast_api_app

    def get_proxy_settings(self) -> ProxySettings:
        if self._cloud.lower() not in ["aws", "azure"]:
            raise Exception("only supported in aws or azure")

        org_id = self._context["tags"]["orgId"]
        org_shard = ""
        # org_shard doesnt need a suffix of "." for dnsname its handled in building the url
        if self._cloud.lower() == "azure":
            org_shard_id = int(org_id) % 20
            org_shard = f".{org_shard_id}"
        cluster_id = self._context["tags"]["clusterId"]
        url_base_path = f"/driver-proxy/o/{org_id}/{cluster_id}/{self._port}"

        from dbruntime.databricks_repl_context import get_context
        host_name = get_context().workspaceUrl
        proxy_url = f"https://{host_name}/driver-proxy/o/{org_id}/{cluster_id}/{self._port}/"

        return ProxySettings(
            proxy_url=proxy_url,
            port=self._port,
            url_base_path=url_base_path
        )

    @property
    def app_url_base_path(self):
        return self._ps.url_base_path

    def mount_gradio_app(self, gradio_app):
        import gradio as gr
        # gradio_app.queue()
        gr.mount_gradio_app(self._fastapi_app, gradio_app, f"/gradio")
        # self._fastapi_app.mount("/gradio", gradio_app)
        self.display_url(self.get_gradio_url())

    def get_cloud(self):
        if self._context["extraContext"]["api_url"].endswith("azuredatabricks.net"):
            return "azure"
        return "aws"

    def get_gradio_url(self):
        # must end with a "/" for it to not redirect
        return f'<a href="{self._ps.proxy_url}gradio/">Click to go to Gradio App!</a>'

    def display_url(self, url):
        self._display_html(url)

    def run(self):
        print(self.app_url_base_path)
        uvicorn.run(self._fastapi_app, host="0.0.0.0", port=self._port)

# COMMAND ----------

import gradio as gr
import random
import time

DESCRIPTION = """
# Simple Chatbot
I'll do my best to answer your question (based on the knowledge stored inside the LLM).
"""

def process_example(message: str, history: str):
    # system_prompt, max_new_tokens, temperature, top_p, top_k
    output = generate_output(message, history)
    return output

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    with gr.Row():
        gr.HTML(
            show_label=False,
            value="<img src='https://databricks.gallerycdn.vsassets.io/extensions/databricks/databricks/0.3.15/1686753455931/Microsoft.VisualStudio.Services.Icons.Default' height='40' width='40'/><div font size='1'></div>",
        )
    gr.Markdown(DESCRIPTION)
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label='User Question'
                    #  , value='Ask your question'
                     )
    clear = gr.ClearButton([msg, chatbot])

    def respond(message, chat_history):
        bot_message = process_example(message, chat_history)
        chat_history.append((message, bot_message))
        time.sleep(2)
        return "", chat_history

    msg.submit(fn=respond,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot])

# COMMAND ----------

app_port = 8766

# COMMAND ----------

cluster_id = dbutils.notebook.entry_point.getDbutils().notebook().getContext().clusterId().getOrElse(None)
workspace_id = dbutils.notebook.entry_point.getDbutils().notebook().getContext().workspaceId().getOrElse(None)

print(f"Use this URL to access the chatbot app: ")
print(f"https://dbc-dp-{workspace_id}.cloud.databricks.com/driver-proxy/o/{workspace_id}/{cluster_id}/{app_port}/gradio/")

# COMMAND ----------

dbx_app = DatabricksApp(app_port)

# demo.queue()
dbx_app.mount_gradio_app(demo)

import nest_asyncio
nest_asyncio.apply()
dbx_app.run()

# COMMAND ----------


