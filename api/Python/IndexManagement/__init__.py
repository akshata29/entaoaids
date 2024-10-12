import logging, json, os
import azure.functions as func
import os
from Utilities.azureBlob import getAllBlobs
from Utilities.cogSearch import deleteSearchIndex
from azure.storage.blob import BlobClient
from Utilities.envVars import *
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    logging.info(f'{context.function_name} HTTP trigger function processed a request.')
    if hasattr(context, 'retry_context'):
        logging.info(f'Current retry count: {context.retry_context.retry_count}')

        if context.retry_context.retry_count == context.retry_context.max_retry_count:
            logging.info(
                f"Max retries of {context.retry_context.max_retry_count} for "
                f"function {context.function_name} has been reached")

    try:
        indexType = req.params.get('indexType')
        indexName = req.params.get('indexName')
        blobName = req.params.get('blobName')
        indexNs = req.params.get('indexNs')
        if (indexNs == None or indexNs == 'null'):
            indexNs = ''
        operation = req.params.get('operation')
        body = json.dumps(req.get_json())
    except ValueError:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )

    if body:
        result = ComposeResponse(indexType, indexName, blobName, indexNs, operation, body)
        return func.HttpResponse(result, mimetype="application/json")
    else:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )

def ComposeResponse(indexType, indexName, blobName, indexNs, operation, jsonData):
    values = json.loads(jsonData)['values']

    logging.info("Calling Compose Response")
    # Prepare the Output before the loop
    results = {}
    results["values"] = []

    for value in values:
        outputRecord = TransformValue(indexType, indexName,  blobName, indexNs, operation, value)
        if outputRecord != None:
            results["values"].append(outputRecord)
    return json.dumps(results, ensure_ascii=False)

def IndexManagement(indexType, indexName, blobName, indexNs, operation, record):
    try:
        if operation == "delete":
            logging.info("Deleting index " + indexNs)
            if indexType == "cogsearch" or indexType == "cogsearchvs":
                deleteSearchIndex(indexNs)
            blobList = getAllBlobs(TenantId, ClientId, ClientSecret, BlobAccountName, OpenAiDocContainer)
            credentials = ClientSecretCredential(TenantId, ClientId, ClientSecret)
            blobService = BlobServiceClient(
                    "https://{}.blob.core.windows.net".format(BlobAccountName), credential=credentials)
            for blob in blobList:
                try:
                    if (blob.metadata['indexName'] == indexName):
                        logging.info("Deleting blob " + blob.name)
                        blobClient = blobService.get_blob_client(OpenAiDocContainer, blob=blob.name)
                        #blobClient = BlobClient.from_connection_string(conn_str=OpenAiDocConnStr, container_name=OpenAiDocContainer, blob_name=blob.name)
                        blobClient.delete_blob()
                except:
                    continue
            return "Success"
        elif operation == "update":
            return "Success"
    except Exception as e:
        logging.error(e)
        return func.HttpResponse(
            "Error getting files",
            status_code=500
        )

def TransformValue(indexType, indexName, blobName, indexNs, operation, record):
    logging.info("Calling Transform Value")
    try:
        recordId = record['recordId']
    except AssertionError  as error:
        return None

    # Validate the inputs
    try:
        assert ('data' in record), "'data' field is required."
        data = record['data']
        assert ('text' in data), "'text' field is required in 'data' object."

    except KeyError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "KeyError:" + error.args[0] }   ]
            })
    except AssertionError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "AssertionError:" + error.args[0] }   ]
            })
    except SystemError as error:
        return (
            {
            "recordId": recordId,
            "errors": [ { "message": "SystemError:" + error.args[0] }   ]
            })

    try:
        # Getting the items from the values/data/text
        value = data['text']
        logging.info("Value: " + value)
        logging.info("Index Type: " + indexType)
        logging.info("Index Name: " + indexName)
        logging.info("Blob Name: " + blobName)
        logging.info("Index Namespace: " + indexNs)
        logging.info("Operation: " + operation)

        indexResponse = IndexManagement(indexType, indexName, blobName, indexNs, operation, value)

        return ({
            "recordId": recordId,
            "data": {
                "error": indexResponse
                    }
            })

    except:
        return (
            {
            "recordId": recordId,
                "data": {
                "error": "Could not process the request"
                    }
            })
