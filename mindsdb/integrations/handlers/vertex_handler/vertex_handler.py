import pandas as pd
import json
from mindsdb.integrations.libs.base import BaseMLEngine
from mindsdb.integrations.handlers.vertex_handler.vertex_client import VertexClient
from mindsdb.utilities import log


class VertexHandler(BaseMLEngine):
    """Handler for the Vertex Google AI cloud API"""

    name = "Vertex"

    def create(self, target, df, args={}):
        """Logs in to Vertex and deploy a pre-trained model to an endpoint.

        If the endpoint already exists for the model, we do nothing.

        If the endpoint does not exist, we create it and deploy the model to it.
        The runtime for this is long, it took 15 minutes for a small model.
        """
        assert "using" in args, "Must provide USING arguments for this handler"
        model_name = args["using"]["model_name"]
        service_key_path = args["using"]["service_key_path"]
        vertex_args_path = args["using"]["vertex_args_path"]
        with open(vertex_args_path) as f:
            vertex_args = json.load(f)
        vertex = VertexClient(service_key_path, vertex_args)

        model = vertex.get_model_by_display_name(model_name)
        if not model:
            raise Exception(f"Vertex model {model_name} not found")
        endpoint_name = model_name + "_endpoint"
        if vertex.get_endpoint_by_display_name(endpoint_name):
            log.logger.info(f"Endpoint {endpoint_name} already exists, skipping deployment")
        else:
            log.logger.info(f"Starting deployment at {endpoint_name}")
            endpoint = vertex.deploy_model(model)
            endpoint.display_name = endpoint_name
            endpoint.update()
            log.logger.info(f"Endpoint {endpoint_name} deployed")

        predict_args = {}
        custom_model = False if "custom_model" not in args["using"] else args["using"]["custom_model"]
        predict_args["endpoint_name"] = endpoint_name
        predict_args["custom_model"] = custom_model
        predict_args["service_key_path"] = service_key_path
        self.model_storage.json_set("predict_args", predict_args)
        self.model_storage.json_set("vertex_args", vertex_args)

    def predict(self, df, args={}):
        """Predict using the deployed model by calling the endpoint."""
        if "__mindsdb_row_id" in df.columns:
            df.drop("__mindsdb_row_id", axis=1, inplace=True)
        predict_args = self.model_storage.json_get("predict_args")
        vertex_args = self.model_storage.json_get("vertex_args")
        vertex = VertexClient(predict_args["service_key_path"], vertex_args)
        results = vertex.predict_from_df(predict_args["endpoint_name"], df, custom_model=predict_args["custom_model"])
        if predict_args["custom_model"]:
            return pd.DataFrame(results.predictions, columns=["prediction"])
        else:
            return pd.DataFrame(results.predictions)